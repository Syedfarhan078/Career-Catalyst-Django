import subprocess
import tempfile
import os
import sys
import json

def run_code(code_str, test_cases):
    """
    Executes a Python code block and verifies it against a list of test cases.
    Each test case must be a dictionary like:
      {"input": "5", "expected": "120", "function": "factorial"}
      or
      {"input": "[2, 7, 11, 15], 9", "expected": "[0, 1]", "function": "two_sum"}
    """
    # Build wrapper injector code
    injector = f"""
import json
import sys

# Injected test cases
test_cases = {repr(test_cases)}
results = []
all_passed = True

for idx, case in enumerate(test_cases):
    func_name = case.get("function", "")
    args_str = case.get("input", "")
    expected_raw = case.get("expected", "")
    
    try:
        # Evaluate function in local namespace
        expr = f"{{func_name}}({{args_str}})"
        val = eval(expr)
        
        # Load expected value from json if possible
        try:
            expected_val = json.loads(expected_raw)
        except Exception:
            expected_val = expected_raw
            
        # Compare output
        if val == expected_val:
            results.append({{"case": idx + 1, "passed": True, "output": val, "expected": expected_val}})
        else:
            all_passed = False
            results.append({{"case": idx + 1, "passed": False, "output": val, "expected": expected_val}})
            
    except Exception as e:
        all_passed = False
        results.append({{"case": idx + 1, "passed": False, "output": f"Runtime Error: {{str(e)}}", "expected": expected_raw}})

# Print result structure
print("---TEST_RESULTS_START---")
print(json.dumps({{"success": all_passed, "results": results}}))
print("---TEST_RESULTS_END---")
"""
    # Combine code
    full_source = code_str + "\n" + injector

    # Write to a temp file
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"runner_{os.getpid()}.py")
    
    try:
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(full_source)
            
        # Run subprocess with timeout (2 seconds)
        # Using sys.executable to ensure we use the virtualenv python
        process = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        
        stdout_content = process.stdout
        stderr_content = process.stderr
        
        if process.returncode != 0:
            return {
                "success": False,
                "error": stderr_content or f"Process exited with non-zero code {process.returncode}",
                "results": []
            }
            
        # Parse output between delimiters
        if "---TEST_RESULTS_START---" in stdout_content:
            try:
                parts = stdout_content.split("---TEST_RESULTS_START---")[1].split("---TEST_RESULTS_END---")
                json_data = json.loads(parts[0].strip())
                return json_data
            except Exception as pe:
                return {
                    "success": False,
                    "error": f"Failed to parse test outputs: {str(pe)}\nStdout: {stdout_content}",
                    "results": []
                }
        else:
            return {
                "success": False,
                "error": f"Syntax Error or crash before evaluation.\nStderr: {stderr_content}\nStdout: {stdout_content}",
                "results": []
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Execution Timeout: Your code took longer than 2.0 seconds to execute. Watch out for infinite loops!",
            "results": []
        }
    except Exception as ge:
        return {
            "success": False,
            "error": f"Runner Internal Error: {str(ge)}",
            "results": []
        }
    finally:
        # Cleanup
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
