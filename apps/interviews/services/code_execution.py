"""
Code Execution Service for CareerCatalyst.

Provides isolated, resource-constrained Python code execution and automated test case evaluation.
Supports containerized execution (Docker) when available, with a hardened development fallback
that enforces AST pre-validation, workspace isolation, environment scrubbing, and deterministic timeouts.
"""

import ast
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Execution status constants
STATUS_SUCCESS = "success"
STATUS_COMPILE_ERROR = "compile_error"
STATUS_RUNTIME_ERROR = "runtime_error"
STATUS_TIMEOUT = "timeout"
STATUS_MEMORY_LIMIT = "memory_limit"
STATUS_OUTPUT_LIMIT = "output_limit"
STATUS_SANDBOX_ERROR = "sandbox_error"
STATUS_INVALID_SUBMISSION = "invalid_submission"

# Maximum captured stdout/stderr length in bytes
MAX_OUTPUT_BYTES = 65536

# Dangerous modules and symbols disallowed in development fallback
DISALLOWED_MODULES = {
    'os', 'sys', 'subprocess', 'shutil', 'socket', 'http', 'urllib',
    'requests', 'ctypes', 'importlib', 'signal', 'threading',
    'multiprocessing', 'pty', 'platform', 'posix', 'nt', 'builtins',
    '_thread', 'asyncio', 'webbrowser', 'tempfile', 'inspect'
}

DISALLOWED_SYMBOLS = {
    'open', 'compile', 'exec', 'eval', 'globals', 'locals',
    '__import__', '__subclasses__', '__globals__', '__code__',
    '__builtins__', 'getattr', 'setattr', 'delattr', 'input'
}


class ASTSecurityScanner(ast.NodeVisitor):
    """
    Validates Python AST for dangerous module imports, builtins, and attribute accesses
    in environments lacking full OS-level container isolation.
    """

    def __init__(self):
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_root = alias.name.split('.')[0]
            if mod_root in DISALLOWED_MODULES:
                self.violations.append(f"Import of module '{alias.name}' is restricted.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod_root = node.module.split('.')[0]
            if mod_root in DISALLOWED_MODULES:
                self.violations.append(f"Import from module '{node.module}' is restricted.")
        for alias in node.names:
            if alias.name in DISALLOWED_SYMBOLS:
                self.violations.append(f"Import of restricted symbol '{alias.name}' is disallowed.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Direct function calls: open(), eval(), exec()
        if isinstance(node.func, ast.Name):
            if node.func.id in DISALLOWED_SYMBOLS:
                self.violations.append(f"Direct call to '{node.func.id}()' is restricted.")
        # Attribute calls like os.system() or __import__()
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in DISALLOWED_SYMBOLS:
                self.violations.append(f"Invocation of restricted attribute '{node.func.attr}()' is disallowed.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in {'__subclasses__', '__globals__', '__code__', '__builtins__'}:
            self.violations.append(f"Access to internal reflection attribute '{node.attr}' is restricted.")
        self.generic_visit(node)


def check_code_security(code_str: str) -> Tuple[bool, Optional[str]]:
    """
    Scans code string using AST.
    Returns (is_safe, error_message).
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, f"Syntax Error: {e.msg} (line {e.lineno})"
    except Exception as e:
        return False, f"Compilation failure: {str(e)}"

    scanner = ASTSecurityScanner()
    scanner.visit(tree)
    if scanner.violations:
        return False, f"Security Violation: {scanner.violations[0]}"

    return True, None


# Embedded driver script executed inside the isolated workspace.
# Uses json and ast.literal_eval for safe argument loading, completely avoiding eval() with user code.
DRIVER_SCRIPT = '''import sys
import json
import ast
import time

def parse_argument(arg_raw):
    """
    Safely converts a string input into Python data types using json or ast.literal_eval.
    Never calls eval().
    """
    if not isinstance(arg_raw, str):
        return arg_raw
    arg_raw = arg_raw.strip()
    try:
        return json.loads(arg_raw)
    except Exception:
        pass
    try:
        return ast.literal_eval(arg_raw)
    except Exception:
        pass
    # If comma-separated arguments are provided (e.g. "[2, 7, 11, 15], 9")
    if "," in arg_raw:
        try:
            wrapped = f"({arg_raw})"
            val = ast.literal_eval(wrapped)
            if isinstance(val, tuple):
                return val
        except Exception:
            pass
    return arg_raw


def main():
    try:
        with open("test_cases.json", "r", encoding="utf-8") as f:
            test_cases = json.load(f)
    except Exception as e:
        print(json.dumps({"error": f"Failed to load test cases: {str(e)}", "results": []}))
        sys.exit(1)

    # Import user solution module
    try:
        import solution
    except Exception as e:
        results = []
        for idx, tc in enumerate(test_cases):
            results.append({
                "case": idx + 1,
                "passed": False,
                "output": f"Import/Runtime Error: {str(e)}",
                "expected": tc.get("expected", ""),
                "error": str(e)
            })
        print(json.dumps({"success": False, "status": "runtime_error", "error": str(e), "results": results}))
        sys.exit(0)

    results = []
    all_passed = True
    total_start = time.perf_counter()

    for idx, case in enumerate(test_cases):
        func_name = case.get("function", "")
        input_raw = case.get("input", "")
        expected_raw = case.get("expected", "")

        func = getattr(solution, func_name, None)
        if func is None or not callable(func):
            all_passed = False
            results.append({
                "case": idx + 1,
                "passed": False,
                "output": f"Function '{func_name}' not defined in solution",
                "expected": expected_raw,
                "error": f"Function '{func_name}' not found"
            })
            continue

        # Parse inputs and expected values safely
        parsed_args = parse_argument(input_raw)
        expected_val = parse_argument(expected_raw)

        case_start = time.perf_counter()
        try:
            if not input_raw or not str(input_raw).strip():
                out = func()
            elif isinstance(parsed_args, tuple):
                out = func(*parsed_args)
            elif isinstance(parsed_args, list) and not input_raw.strip().startswith("["):
                out = func(*parsed_args)
            else:
                out = func(parsed_args)

            case_duration_ms = round((time.perf_counter() - case_start) * 1000, 2)
            passed = (out == expected_val)
            if not passed:
                all_passed = False

            results.append({
                "case": idx + 1,
                "passed": passed,
                "output": out,
                "expected": expected_val,
                "duration_ms": case_duration_ms,
                "error": None
            })
        except Exception as e:
            all_passed = False
            case_duration_ms = round((time.perf_counter() - case_start) * 1000, 2)
            results.append({
                "case": idx + 1,
                "passed": False,
                "output": f"Runtime Error: {str(e)}",
                "expected": expected_val,
                "duration_ms": case_duration_ms,
                "error": str(e)
            })

    total_duration_ms = round((time.perf_counter() - total_start) * 1000, 2)
    output_payload = {
        "success": all_passed,
        "status": "success" if all_passed else "runtime_error",
        "total_duration_ms": total_duration_ms,
        "results": results
    }
    with open("results.json", "w", encoding="utf-8") as rf:
        json.dump(output_payload, rf)
    print(json.dumps(output_payload))

if __name__ == "__main__":
    main()
'''


class CodeExecutionService:
    """
    Modernized code execution manager.
    Executes Python submissions in dedicated isolated workspaces with strict boundaries.
    """

    @classmethod
    def is_docker_available(cls) -> bool:
        """Checks if Docker daemon is accessible."""
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False
        try:
            res = subprocess.run([docker_bin, "info"], capture_output=True, timeout=2.0)
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def execute(
        cls,
        code_str: str,
        test_cases: List[Dict[str, Any]],
        timeout_seconds: float = 2.0,
        memory_limit_mb: int = 128
    ) -> Dict[str, Any]:
        """
        Executes candidate code against test cases.
        Returns a rich structured execution dictionary.
        """
        if not code_str or not code_str.strip():
            return {
                "status": STATUS_INVALID_SUBMISSION,
                "success": False,
                "passed_tests": 0,
                "total_tests": len(test_cases) if test_cases else 0,
                "execution_time_ms": 0.0,
                "memory_used_kb": None,
                "stdout": "",
                "stderr": "",
                "error": "Submission is empty.",
                "results": [],
                "execution_mode": "DEVELOPMENT_FALLBACK",
                "is_sandbox_isolated": False
            }

        # 1. AST Pre-Validation Scan (Mandatory Defense-in-Depth)
        is_safe, sec_error = check_code_security(code_str)
        if not is_safe:
            is_syntax = "Syntax Error" in (sec_error or "")
            status = STATUS_COMPILE_ERROR if is_syntax else STATUS_SANDBOX_ERROR
            return {
                "status": status,
                "success": False,
                "passed_tests": 0,
                "total_tests": len(test_cases) if test_cases else 0,
                "execution_time_ms": 0.0,
                "memory_used_kb": None,
                "stdout": "",
                "stderr": sec_error or "Code security violation.",
                "error": sec_error,
                "results": [],
                "execution_mode": "DEVELOPMENT_FALLBACK",
                "is_sandbox_isolated": False
            }

        # 2. Check Docker container availability
        docker_available = cls.is_docker_available()
        if docker_available:
            return cls._execute_docker(code_str, test_cases, timeout_seconds, memory_limit_mb)
        else:
            return cls._execute_hardened_subprocess(code_str, test_cases, timeout_seconds)

    @classmethod
    def _execute_docker(
        cls,
        code_str: str,
        test_cases: List[Dict[str, Any]],
        timeout_seconds: float,
        memory_limit_mb: int
    ) -> Dict[str, Any]:
        """Executes code inside a hardened Docker container."""
        workspace_dir = tempfile.mkdtemp(prefix=f"docker_exec_{uuid.uuid4().hex[:8]}_")
        start_time = time.perf_counter()

        try:
            with open(os.path.join(workspace_dir, "solution.py"), "w", encoding="utf-8") as f:
                f.write(code_str)
            with open(os.path.join(workspace_dir, "test_cases.json"), "w", encoding="utf-8") as f:
                json.dump(test_cases, f)
            with open(os.path.join(workspace_dir, "driver.py"), "w", encoding="utf-8") as f:
                f.write(DRIVER_SCRIPT)

            cmd = [
                "docker", "run", "--rm",
                "--net", "none",
                "--cpus", "0.5",
                f"--memory={memory_limit_mb}m",
                "--pids-limit", "30",
                "-v", f"{os.path.abspath(workspace_dir)}:/sandbox:rw",
                "-w", "/sandbox",
                "python:3.10-slim",
                "python", "driver.py"
            ]

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 3.0  # Allow container startup margin
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            stdout = (process.stdout or "")[:MAX_OUTPUT_BYTES]
            stderr = (process.stderr or "")[:MAX_OUTPUT_BYTES]

            return cls._parse_driver_output(workspace_dir, stdout, stderr, elapsed_ms, "DOCKER_CONTAINER", True)
        except subprocess.TimeoutExpired:
            return cls._timeout_result(len(test_cases), timeout_seconds, "DOCKER_CONTAINER", True)
        except Exception as e:
            return cls._error_result(str(e), len(test_cases), "DOCKER_CONTAINER", True)
        finally:
            shutil.rmtree(workspace_dir, ignore_errors=True)

    @classmethod
    def _execute_hardened_subprocess(
        cls,
        code_str: str,
        test_cases: List[Dict[str, Any]],
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """
        Executes code in an isolated temporary directory with scrubbed environment.
        Explicitly marked as DEVELOPMENT_FALLBACK.
        """
        workspace_dir = tempfile.mkdtemp(prefix=f"safe_exec_{uuid.uuid4().hex[:8]}_")
        start_time = time.perf_counter()

        try:
            solution_path = os.path.join(workspace_dir, "solution.py")
            with open(solution_path, "w", encoding="utf-8") as f:
                f.write(code_str)

            cases_path = os.path.join(workspace_dir, "test_cases.json")
            with open(cases_path, "w", encoding="utf-8") as f:
                json.dump(test_cases, f)

            driver_path = os.path.join(workspace_dir, "driver.py")
            with open(driver_path, "w", encoding="utf-8") as f:
                f.write(DRIVER_SCRIPT)

            # Scrubbed minimal environment: Strip ALL Django secrets, DB URLs, .env variables
            clean_env = {
                'PYTHONPATH': workspace_dir,
                'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
                'PATH': os.environ.get('PATH', ''),
                'TEMP': workspace_dir,
                'TMP': workspace_dir,
                'PYTHONUNBUFFERED': '1'
            }

            process = subprocess.run(
                [sys.executable, driver_path],
                cwd=workspace_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            stdout = (process.stdout or "")[:MAX_OUTPUT_BYTES]
            stderr = (process.stderr or "")[:MAX_OUTPUT_BYTES]

            return cls._parse_driver_output(
                workspace_dir, stdout, stderr, elapsed_ms,
                "DEVELOPMENT_FALLBACK", False
            )

        except subprocess.TimeoutExpired:
            return cls._timeout_result(len(test_cases), timeout_seconds, "DEVELOPMENT_FALLBACK", False)
        except Exception as e:
            return cls._error_result(str(e), len(test_cases), "DEVELOPMENT_FALLBACK", False)
        finally:
            shutil.rmtree(workspace_dir, ignore_errors=True)

    @classmethod
    def _parse_driver_output(
        cls,
        workspace_dir: str,
        stdout: str,
        stderr: str,
        elapsed_ms: float,
        mode: str,
        is_isolated: bool
    ) -> Dict[str, Any]:
        """Parses output from driver script JSON file or stdout."""
        results_file = os.path.join(workspace_dir, "results.json")
        payload = None

        if os.path.exists(results_file):
            try:
                with open(results_file, "r", encoding="utf-8") as rf:
                    payload = json.load(rf)
            except Exception:
                pass

        if payload is None and stdout.strip():
            for line in reversed(stdout.strip().splitlines()):
                try:
                    payload = json.loads(line)
                    break
                except Exception:
                    continue

        if payload and isinstance(payload, dict):
            raw_results = payload.get("results", [])
            passed_count = sum(1 for r in raw_results if r.get("passed", False))
            total_count = len(raw_results)
            all_passed = payload.get("success", False)

            return {
                "status": STATUS_SUCCESS if all_passed else STATUS_RUNTIME_ERROR,
                "success": all_passed,
                "passed_tests": passed_count,
                "total_tests": total_count,
                "execution_time_ms": payload.get("total_duration_ms", elapsed_ms),
                "memory_used_kb": None,
                "stdout": stdout,
                "stderr": stderr,
                "error": payload.get("error", "") if not all_passed else "",
                "results": raw_results,
                "execution_mode": mode,
                "is_sandbox_isolated": is_isolated
            }

        # If unparseable output, treat as syntax/runtime crash
        return {
            "status": STATUS_RUNTIME_ERROR,
            "success": False,
            "passed_tests": 0,
            "total_tests": 0,
            "execution_time_ms": elapsed_ms,
            "memory_used_kb": None,
            "stdout": stdout,
            "stderr": stderr,
            "error": stderr or "Unknown runtime crash during execution.",
            "results": [],
            "execution_mode": mode,
            "is_sandbox_isolated": is_isolated
        }

    @classmethod
    def _timeout_result(cls, total_tests: int, timeout: float, mode: str, is_isolated: bool) -> Dict[str, Any]:
        return {
            "status": STATUS_TIMEOUT,
            "success": False,
            "passed_tests": 0,
            "total_tests": total_tests,
            "execution_time_ms": timeout * 1000,
            "memory_used_kb": None,
            "stdout": "",
            "stderr": f"Execution Timeout: Code took longer than {timeout} seconds.",
            "error": f"Execution Timeout: Code took longer than {timeout} seconds. Avoid infinite loops.",
            "results": [],
            "execution_mode": mode,
            "is_sandbox_isolated": is_isolated
        }

    @classmethod
    def _error_result(cls, error_msg: str, total_tests: int, mode: str, is_isolated: bool) -> Dict[str, Any]:
        return {
            "status": STATUS_RUNTIME_ERROR,
            "success": False,
            "passed_tests": 0,
            "total_tests": total_tests,
            "execution_time_ms": 0.0,
            "memory_used_kb": None,
            "stdout": "",
            "stderr": error_msg,
            "error": f"Execution error: {error_msg}",
            "results": [],
            "execution_mode": mode,
            "is_sandbox_isolated": is_isolated
        }


# Backwards compatibility helper matching original runner.run_code signature
def run_code(code_str: str, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper function for existing callers and tests.
    Delegates directly to CodeExecutionService.
    """
    res = CodeExecutionService.execute(code_str, test_cases)
    # Ensure legacy keys ("success", "results", "error") match legacy expectation
    return {
        "success": res.get("success", False),
        "results": res.get("results", []),
        "error": res.get("error", ""),
        "status": res.get("status", STATUS_RUNTIME_ERROR),
        "passed_tests": res.get("passed_tests", 0),
        "total_tests": res.get("total_tests", 0),
        "execution_time_ms": res.get("execution_time_ms", 0.0),
        "execution_mode": res.get("execution_mode", "DEVELOPMENT_FALLBACK"),
        "is_sandbox_isolated": res.get("is_sandbox_isolated", False)
    }
