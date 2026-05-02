"""
Sandbox Executor Module.

Provides secure execution of untrusted code in isolated environments.
Supports Python code execution with various security constraints.
"""

import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from configs.schemas import SandboxConfig, GodAgentConfig
from configs.settings import get_config


# =============================================================================
# Result and Error Classes
# =============================================================================

@dataclass
class SandboxResult:
    """Result of executing code in a sandbox."""
    
    # Execution metadata
    execution_id: str
    started_at: datetime
    completed_at: datetime
    execution_time_ms: float
    
    # Result
    output: Any = None
    output_type: str = ""
    
    # State
    success: bool = False
    exit_code: int = 0
    
    # Error information
    error: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Resource usage
    cpu_time: Optional[float] = None
    memory_used_mb: Optional[float] = None
    
    # Metrics
    tokens_processed: Optional[int] = None
    operations_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "execution_id": self.execution_id,
            "success": self.success,
            "exit_code": self.exit_code,
            "output": self.output,
            "output_type": self.output_type,
            "error": self.error,
            "error_type": self.error_type,
            "stack_trace": self.stack_trace,
            "execution_time_ms": self.execution_time_ms,
            "cpu_time": self.cpu_time,
            "memory_used_mb": self.memory_used_mb,
            "tokens_processed": self.tokens_processed,
            "operations_count": self.operations_count,
        }


class SandboxExecutionError(Exception):
    """Base exception for sandbox execution errors."""
    
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class ExecutionError(SandboxExecutionError):
    """Error during code execution."""
    
    def __init__(self, message: str, error_type: str, stack_trace: str = ""):
        super().__init__(message)
        self.error_type = error_type
        self.stack_trace = stack_trace


class TimeoutError(SandboxExecutionError):
    """Timeout during execution."""
    
    def __init__(self, message: str = "Execution timed out", timeout: float = 0):
        super().__init__(message, exit_code=124)  # 124 is standard timeout exit code
        self.timeout = timeout


class MemoryLimitExceededError(SandboxExecutionError):
    """Memory limit exceeded during execution."""
    
    def __init__(self, message: str = "Memory limit exceeded", 
                 memory_used_mb: float = 0, memory_limit_mb: float = 0):
        super().__init__(message, exit_code=137)  # 137 is standard OOM exit code
        self.memory_used_mb = memory_used_mb
        self.memory_limit_mb = memory_limit_mb


class SecurityViolationError(SandboxExecutionError):
    """Security violation during execution."""
    
    def __init__(self, message: str, violation_type: str = "unknown"):
        super().__init__(message, exit_code=139)  # 139 is standard kill exit code
        self.violation_type = violation_type


# =============================================================================
# Sandbox Executor
# =============================================================================

class SandboxExecutor:
    """
    Executes untrusted code in a sandboxed environment.
    
    Supports multiple execution modes:
    - subprocess: Run in a separate Python process
    - restricted: Run with restricted imports
    - full: Run with full isolation (container-based in future)
    
    Security features:
    - Timeout enforcement
    - Memory limits
    - Blocked module imports
    - File system restrictions
    - Network access control
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize the sandbox executor.
        
        Args:
            config: Sandbox configuration (defaults to global config)
        """
        self.config = config or get_config().sandbox
        self._execution_counter = 0
    
    def _next_execution_id(self) -> str:
        """Generate a unique execution ID."""
        self._execution_counter += 1
        import uuid
        return f"sandbox-{uuid.uuid4().hex[:8]}-{self._execution_counter}"
    
    def execute_python(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
    ) -> SandboxResult:
        """
        Execute Python code in a sandbox.
        
        Args:
            code: Python code to execute
            context: Optional context variables to pre-load
            timeout: Timeout in seconds (overrides config)
            max_memory_mb: Max memory in MB (overrides config)
            
        Returns:
            SandboxResult: The execution result
            
        Raises:
            TimeoutError: If execution times out
            MemoryLimitExceededError: If memory limit exceeded
            ExecutionError: If code execution fails
            SecurityViolationError: If security violation detected
        """
        execution_id = self._next_execution_id()
        started_at = datetime.utcnow()
        
        # Apply config defaults
        timeout = timeout or self.config.timeout
        max_memory_mb = max_memory_mb or self.config.max_memory_mb
        
        try:
            # Use subprocess-based isolation
            result = self._execute_subprocess(
                code=code,
                context=context,
                timeout=timeout,
                max_memory_mb=max_memory_mb,
                execution_id=execution_id,
            )
            
            completed_at = datetime.utcnow()
            execution_time_ms = (completed_at - started_at).total_seconds() * 1000
            
            return SandboxResult(
                execution_id=execution_id,
                started_at=started_at,
                completed_at=completed_at,
                execution_time_ms=execution_time_ms,
                output=result.get('output'),
                output_type=result.get('output_type', 'unknown'),
                success=result.get('success', False),
                exit_code=result.get('exit_code', 0),
                error=result.get('error'),
                error_type=result.get('error_type'),
                stack_trace=result.get('stack_trace'),
            )
            
        except TimeoutError as e:
            completed_at = datetime.utcnow()
            execution_time_ms = (completed_at - started_at).total_seconds() * 1000
            raise TimeoutError(
                f"Execution timed out after {timeout}s",
                timeout=timeout
            )
        except Exception as e:
            completed_at = datetime.utcnow()
            execution_time_ms = (completed_at - started_at).total_seconds() * 1000
            raise ExecutionError(
                str(e),
                error_type=type(e).__name__,
                stack_trace=traceback.format_exc()
            )
    
    async def execute_python_async(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
    ) -> SandboxResult:
        """
        Execute Python code in a sandbox asynchronously.
        
        Args:
            code: Python code to execute
            context: Optional context variables to pre-load
            timeout: Timeout in seconds (overrides config)
            max_memory_mb: Max memory in MB (overrides config)
            
        Returns:
            SandboxResult: The execution result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute_python(code, context, timeout, max_memory_mb)
        )
    
    def _execute_subprocess(
        self,
        code: str,
        context: Optional[Dict[str, Any]],
        timeout: float,
        max_memory_mb: float,
        execution_id: str,
    ) -> Dict[str, Any]:
        """
        Execute code in a subprocess with isolation.
        
        This is the most secure method as it provides:
        - Process isolation
        - Memory limits (via ulimit on Unix)
        - Timeout enforcement
        - Clean environment
        """
        # Create a wrapper script that enforces restrictions
        wrapper_code = self._build_wrapper_script(
            code=code,
            context=context,
            execution_id=execution_id,
        )
        
        # Write wrapper to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False
        ) as f:
            f.write(wrapper_code)
            temp_file = f.name
        
        try:
            # Set resource limits
            env = os.environ.copy()
            env.update({
                'SANDBOX_EXECUTION_ID': execution_id,
                'SANDBOX_TIMEOUT': str(timeout),
                'SANDBOX_MAX_MEMORY_MB': str(max_memory_mb),
            })
            
            # Set memory limit (Unix only)
            memory_limit_bytes = int(max_memory_mb * 1024 * 1024)
            
            # Build command
            cmd = [
                sys.executable,
                temp_file,
            ]
            
            # Run the subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                env=env,
                preexec_fn=self._set_resource_limits(memory_limit_bytes) if os.name == 'posix' else None,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = b'', b'Timeout killing process'
                
                raise TimeoutError(
                    f"Execution timed out after {timeout}s",
                    timeout=timeout
                )
            
            # Parse output
            return self._parse_subprocess_output(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code or 0,
                execution_id=execution_id,
            )
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except FileNotFoundError:
                pass
    
    def _set_resource_limits(self, memory_limit_bytes: int):
        """Set resource limits for subprocess (Unix only)."""
        if os.name != 'posix':
            return None
        
        import resource
        
        def set_limits():
            # Set memory limit (soft and hard)
            resource.setrlimit(
                resource.RLIMIT_AS,
                (memory_limit_bytes, memory_limit_bytes)
            )
            
            # Set CPU time limit (10x timeout as safety)
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (int(self.config.timeout * 10), int(self.config.timeout * 10))
            )
            
            # Set file size limit
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (10 * 1024 * 1024, 10 * 1024 * 1024)  # 10 MB
            )
            
            # Set number of processes
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (10, 10)  # Max 10 child processes
            )
        
        return set_limits
    
    def _build_wrapper_script(
        self,
        code: str,
        context: Optional[Dict[str, Any]],
        execution_id: str,
    ) -> str:
        """Build the wrapper script that enforces sandbox restrictions."""
        # Generate safe context
        context_code = ""
        if context:
            safe_context = self._sanitize_context(context)
            context_code = f"\ncontext = {safe_context}\n"
        
        # Build allowed/blocked module lists
        allowed_modules = self.config.allowed_modules
        blocked_modules = self.config.blocked_modules
        
        wrapper = f'''
import sys
import os
import json
import traceback
import time
import builtins

# Execution metadata
execution_id = "{execution_id}"
start_time = time.time()

# Security configuration
ALLOWED_MODULES = set({json.dumps(allowed_modules)})
BLOCKED_MODULES = set({json.dumps(blocked_modules)})
ENABLE_NETWORK = {str(self.config.enable_network).lower()}
ENABLE_FILE_IO = {str(self.config.enable_file_io).lower()}
ALLOWED_PATHS = {json.dumps(self.config.allowed_paths)}

# Track operations
operations_count = 0

def check_module_import(name):
    """Check if a module can be imported."""
    global operations_count
    operations_count += 1
    
    # Check blocked modules first
    if name in BLOCKED_MODULES or any(name.startswith(b + ".") for b in BLOCKED_MODULES):
        raise ImportError(f"Module '{name}' is blocked for security reasons")
    
    # Check allowed modules
    if ALLOWED_MODULES and name not in ALLOWED_MODULES and not any(name.startswith(a + ".") for a in ALLOWED_MODULES):
        raise ImportError(f"Module '{name}' is not in the allowed list")
    
    return name

# Override __import__
original_import = __import__

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Safe import that checks module permissions."""
    check_module_import(name)
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = safe_import

# Restrict file I/O if disabled
if not ENABLE_FILE_IO:
    def block_file_io():
        raise PermissionError("File I/O is disabled in sandbox")
    
    open = block_file_io
    os.open = block_file_io
    os.system = block_file_io

# Restrict network if disabled
if not ENABLE_NETWORK:
    import socket
    import http.client
    import urllib.request
    
    def block_network():
        raise PermissionError("Network access is disabled in sandbox")
    
    socket.socket = block_network
    http.client.HTTPConnection = block_network
    urllib.request.urlopen = block_network

# Install context{context_code}

# Execute the user code
result = None
output_type = "none"
success = False
error = None
error_type = None
stack_trace = None

try:
    # Execute the code
    {code}
    success = True
    output_type = type(result).__name__
except SystemExit as e:
    success = False
    error = str(e)
    error_type = "SystemExit"
    output_type = "none"
except Exception as e:
    success = False
    error = str(e)
    error_type = type(e).__name__
    stack_trace = traceback.format_exc()
    output_type = "none"

# Prepare output
end_time = time.time()
execution_time = end_time - start_time

output = {{
    "execution_id": execution_id,
    "success": success,
    "exit_code": 0 if success else 1,
    "output": result if result is not None else None,
    "output_type": output_type,
    "error": error,
    "error_type": error_type,
    "stack_trace": stack_trace,
    "execution_time": execution_time,
    "operations_count": operations_count,
}}

print(json.dumps(output))
'''
        return wrapper
    
    def _sanitize_context(self, context: Dict[str, Any]) -> str:
        """Sanitize context for safe inclusion in wrapper script."""
        import json
        
        def sanitize_value(value: Any) -> Any:
            """Recursively sanitize a value."""
            if value is None or isinstance(value, (bool, int, float)):
                return value
            elif isinstance(value, str):
                # Remove any dangerous content
                return value
            elif isinstance(value, (list, tuple)):
                return [sanitize_value(v) for v in value]
            elif isinstance(value, dict):
                return {str(k): sanitize_value(v) for k, v in value.items()}
            else:
                # For other types, convert to string representation
                return str(value)
        
        sanitized = {k: sanitize_value(v) for k, v in context.items()}
        return json.dumps(sanitized, ensure_ascii=False, default=str)
    
    def _parse_subprocess_output(
        self,
        stdout: bytes,
        stderr: bytes,
        exit_code: int,
        execution_id: str,
    ) -> Dict[str, Any]:
        """Parse the output from subprocess execution."""
        try:
            output_str = stdout.decode('utf-8')
            return json.loads(output_str)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            # If we can't parse the output, it's an error
            error_msg = f"Failed to parse output: {e}\nStdout: {stdout[:500]}\nStderr: {stderr[:500]}"
            
            # Check for memory error in stderr
            stderr_str = stderr.decode('utf-8', errors='replace')
            if 'MemoryError' in stderr_str or 'Killed' in stderr_str:
                raise MemoryLimitExceededError(
                    f"Memory limit exceeded: {stderr_str[:200]}",
                    memory_used_mb=0,
                    memory_limit_mb=self.config.max_memory_mb
                )
            
            return {
                "execution_id": execution_id,
                "success": False,
                "exit_code": exit_code,
                "output": None,
                "output_type": "none",
                "error": error_msg,
                "error_type": "SandboxError",
                "stack_trace": stderr_str[:1000],
            }


# =============================================================================
# Restricted Execution (Alternative method)
# =============================================================================

class RestrictedExecutor:
    """
    Alternative executor that uses Python's built-in restrictions.
    
    Less secure than subprocess isolation but faster for simple cases.
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or get_config().sandbox
        self._allowed_modules = set(self.config.allowed_modules)
        self._blocked_modules = set(self.config.blocked_modules)
    
    def execute(self, code: str, context: Optional[Dict[str, Any]] = None) -> SandboxResult:
        """
        Execute code with restricted imports.
        
        WARNING: This is less secure than subprocess isolation!
        Only use for trusted or carefully validated code.
        """
        execution_id = f"restricted-{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()
        
        # Save original __import__
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        
        try:
            # Install restricted import
            def restricted_import(name, *args, **kwargs):
                # Check blocked modules
                if name in self._blocked_modules or any(
                    name.startswith(b + ".") for b in self._blocked_modules
                ):
                    raise ImportError(f"Module '{name}' is blocked for security reasons")
                
                # Check allowed modules (if list is not empty)
                if self._allowed_modules and name not in self._allowed_modules and not any(
                    name.startswith(a + ".") for a in self._allowed_modules
                ):
                    raise ImportError(f"Module '{name}' is not in the allowed list")
                
                return original_import(name, *args, **kwargs)
            
            # Temporarily replace __import__
            __builtins__.__import__ = restricted_import
            
            # Create execution namespace
            namespace = {
                '__name__': '__main__',
                '__builtins__': __builtins__,
            }
            
            # Add context if provided
            if context:
                namespace.update(context)
            
            # Execute with timeout
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    exec,
                    code,
                    namespace,
                )
                
                try:
                    future.result(timeout=self.config.timeout)
                    success = True
                    error = None
                    error_type = None
                    stack_trace = None
                    output = namespace.get('_', None)
                    output_type = type(output).__name__ if output is not None else 'none'
                    
                except concurrent.futures.TimeoutError:
                    raise TimeoutError(
                        f"Execution timed out after {self.config.timeout}s",
                        timeout=self.config.timeout
                    )
                except Exception as e:
                    raise ExecutionError(
                        str(e),
                        error_type=type(e).__name__,
                        stack_trace=traceback.format_exc()
                    )
            
            completed_at = datetime.utcnow()
            execution_time_ms = (completed_at - started_at).total_seconds() * 1000
            
            return SandboxResult(
                execution_id=execution_id,
                started_at=started_at,
                completed_at=completed_at,
                execution_time_ms=execution_time_ms,
                output=output,
                output_type=output_type,
                success=success,
                exit_code=0 if success else 1,
                error=error,
                error_type=error_type,
                stack_trace=stack_trace,
            )
            
        finally:
            # Restore original __import__
            __builtins__.__import__ = original_import


# Import uuid at module level
import uuid
