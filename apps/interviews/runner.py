"""
Legacy Runner Shim.
Forwards all calls to apps.interviews.services.code_execution.run_code
maintaining complete backward compatibility while eliminating RCE vulnerabilities.
"""

from apps.interviews.services.code_execution import (
    run_code,
    CodeExecutionService,
    STATUS_SUCCESS,
    STATUS_COMPILE_ERROR,
    STATUS_RUNTIME_ERROR,
    STATUS_TIMEOUT,
    STATUS_SANDBOX_ERROR
)

__all__ = [
    'run_code',
    'CodeExecutionService',
    'STATUS_SUCCESS',
    'STATUS_COMPILE_ERROR',
    'STATUS_RUNTIME_ERROR',
    'STATUS_TIMEOUT',
    'STATUS_SANDBOX_ERROR'
]
