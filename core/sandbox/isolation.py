"""
Isolation Module.

Provides process and environment isolation for sandboxed execution.
This is a critical security component (Part of the 98.4% harness infrastructure).
"""

import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from configs.settings import get_config
from configs.schemas import SandboxConfig


# =============================================================================
# Isolation Modes
# =============================================================================

class IsolationMode(str, Enum):
    """Isolation modes for sandboxed execution."""
    
    NONE = "none"           # No isolation (not recommended)
    PROCESS = "process"     # Separate process (subprocess)
    NAMESPACE = "namespace" # Unix namespace isolation
    CONTAINER = "container" # Container-based isolation (Docker, etc.)
    CHROOT = "chroot"       # chroot isolation (Unix only)
    
    @classmethod
    def from_string(cls, mode: str) -> 'IsolationMode':
        """Convert string to IsolationMode."""
        try:
            return cls[mode.lower()]
        except KeyError:
            return cls.NONE


# =============================================================================
# Namespace Configuration
# =============================================================================

@dataclass
class Namespace:
    """Configuration for a Linux namespace."""
    
    name: str  # pid, net, mnt, ipc, uts, user, cgroup
    enabled: bool = True
    
    @classmethod
    def from_string(cls, name: str) -> 'Namespace':
        """Create a Namespace from a string."""
        return cls(name=name, enabled=True)


@dataclass
class NamespaceConfig:
    """Configuration for namespace isolation."""
    
    pid: bool = True      # Process ID namespace
    net: bool = True      # Network namespace
    mnt: bool = True      # Mount namespace
    ipc: bool = True      # Inter-process communication namespace
    uts: bool = True      # UTS namespace (hostname)
    user: bool = False    # User namespace (requires root)
    cgroup: bool = False  # Cgroup namespace (requires root)
    
    def get_enabled_namespaces(self) -> List[Namespace]:
        """Get list of enabled namespaces."""
        namespaces = []
        
        if self.pid:
            namespaces.append(Namespace(name="pid"))
        if self.net:
            namespaces.append(Namespace(name="net"))
        if self.mnt:
            namespaces.append(Namespace(name="mnt"))
        if self.ipc:
            namespaces.append(Namespace(name="ipc"))
        if self.uts:
            namespaces.append(Namespace(name="uts"))
        if self.user:
            namespaces.append(Namespace(name="user"))
        if self.cgroup:
            namespaces.append(Namespace(name="cgroup"))
        
        return namespaces
    
    def to_unshare_flags(self) -> List[str]:
        """Convert to unshare command flags."""
        flags = []
        
        if self.pid:
            flags.append("--pid")
        if self.net:
            flags.append("--net")
        if self.mnt:
            flags.append("--mount")
        if self.ipc:
            flags.append("--ipc")
        if self.uts:
            flags.append("--uts")
        if self.user:
            flags.append("--user")
        if self.cgroup:
            flags.append("--cgroup")
        
        return flags


# =============================================================================
# Isolation Manager
# =============================================================================

@dataclass
class IsolationContext:
    """Context for isolated execution."""
    
    isolation_id: str
    mode: IsolationMode
    temp_dir: Optional[Path] = None
    work_dir: Optional[Path] = None
    env: Optional[Dict[str, str]] = None
    namespaces: Optional[NamespaceConfig] = None
    
    def cleanup(self) -> None:
        """Clean up isolation context."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass


class IsolationManager:
    """
    Manages process and environment isolation for sandboxed execution.
    
    Provides multiple isolation strategies:
    - Process isolation (separate Python process)
    - Namespace isolation (Linux namespaces)
    - Container isolation (future)
    - File system isolation (chroot, temp directories)
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize the isolation manager.
        
        Args:
            config: Sandbox configuration
        """
        self.config = config or get_config().sandbox
        self._active_contexts: Dict[str, IsolationContext] = {}
    
    def create_context(self, mode: IsolationMode = IsolationMode.PROCESS) -> IsolationContext:
        """
        Create a new isolation context.
        
        Args:
            mode: Isolation mode to use
            
        Returns:
            IsolationContext: The created context
        """
        isolation_id = str(uuid.uuid4())
        
        # Create temp directory for this isolation context
        temp_dir = None
        work_dir = None
        
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix=f"sandbox-{isolation_id[:8]}-temp-"))
            work_dir = Path(tempfile.mkdtemp(prefix=f"sandbox-{isolation_id[:8]}-work-"))
        except Exception:
            pass
        
        # Create environment
        env = os.environ.copy()
        env.update({
            'SANDBOX_ISOLATION_ID': isolation_id,
            'SANDBOX_ISOLATION_MODE': mode.value,
            'SANDBOX_TEMP_DIR': str(temp_dir) if temp_dir else '',
            'SANDBOX_WORK_DIR': str(work_dir) if work_dir else '',
        })
        
        # Create namespace config
        namespaces = NamespaceConfig() if mode == IsolationMode.NAMESPACE else None
        
        context = IsolationContext(
            isolation_id=isolation_id,
            mode=mode,
            temp_dir=temp_dir,
            work_dir=work_dir,
            env=env,
            namespaces=namespaces,
        )
        
        self._active_contexts[isolation_id] = context
        
        return context
    
    def cleanup_context(self, isolation_id: str) -> None:
        """Clean up an isolation context."""
        if isolation_id in self._active_contexts:
            context = self._active_contexts.pop(isolation_id)
            context.cleanup()
    
    def cleanup_all(self) -> None:
        """Clean up all isolation contexts."""
        for isolation_id in list(self._active_contexts.keys()):
            self.cleanup_context(isolation_id)
    
    def execute_in_context(
        self,
        code: str,
        context: Optional[IsolationContext] = None,
        mode: IsolationMode = IsolationMode.PROCESS,
        timeout: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute code in an isolation context.
        
        Args:
            code: Python code to execute
            context: Isolation context to use (created if None)
            mode: Isolation mode
            timeout: Timeout in seconds
            max_memory_mb: Max memory in MB
            
        Returns:
            Dict with execution results
        """
        if context is None:
            context = self.create_context(mode)
        
        try:
            if mode == IsolationMode.PROCESS:
                return self._execute_in_process(
                    code=code,
                    context=context,
                    timeout=timeout,
                    max_memory_mb=max_memory_mb,
                )
            elif mode == IsolationMode.NAMESPACE:
                return self._execute_in_namespace(
                    code=code,
                    context=context,
                    timeout=timeout,
                    max_memory_mb=max_memory_mb,
                )
            else:
                return self._execute_in_process(
                    code=code,
                    context=context,
                    timeout=timeout,
                    max_memory_mb=max_memory_mb,
                )
        finally:
            if context:
                self.cleanup_context(context.isolation_id)
    
    def _execute_in_process(
        self,
        code: str,
        context: IsolationContext,
        timeout: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute code in a separate process."""
        import json
        import sys
        import traceback
        
        timeout = timeout or self.config.timeout
        max_memory_mb = max_memory_mb or self.config.max_memory_mb
        
        # Create wrapper script
        wrapper = self._build_process_wrapper(
            code=code,
            isolation_id=context.isolation_id,
            temp_dir=str(context.temp_dir) if context.temp_dir else '',
            work_dir=str(context.work_dir) if context.work_dir else '',
        )
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(wrapper)
            temp_script = f.name
        
        try:
            # Set resource limits
            env = context.env or os.environ.copy()
            
            # Calculate memory limit in bytes
            memory_limit_bytes = int(max_memory_mb * 1024 * 1024)
            
            # Build command
            cmd = [sys.executable, temp_script]
            
            # Set up preexec function for resource limits (Unix only)
            preexec_fn = None
            if os.name == 'posix':
                import resource
                
                def set_limits():
                    # Memory limit
                    resource.setrlimit(
                        resource.RLIMIT_AS,
                        (memory_limit_bytes, memory_limit_bytes)
                    )
                    # CPU time limit
                    resource.setrlimit(
                        resource.RLIMIT_CPU,
                        (int(timeout * 10), int(timeout * 10))
                    )
                    # File size limit
                    resource.setrlimit(
                        resource.RLIMIT_FSIZE,
                        (10 * 1024 * 1024, 10 * 1024 * 1024)  # 10 MB
                    )
                    # Number of processes
                    resource.setrlimit(
                        resource.RLIMIT_NPROC,
                        (10, 10)
                    )
                
                preexec_fn = set_limits
            
            # Run subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                env=env,
                preexec_fn=preexec_fn,
                cwd=str(context.work_dir) if context.work_dir else None,
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
                    stdout, stderr = b'', b'Timeout'
                
                return {
                    "success": False,
                    "exit_code": 124,  # Timeout exit code
                    "output": None,
                    "error": "Execution timed out",
                    "error_type": "TimeoutError",
                    "stack_trace": "",
                }
            
            # Parse output
            try:
                output_str = stdout.decode('utf-8')
                result = json.loads(output_str)
                return result
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                stderr_str = stderr.decode('utf-8', errors='replace')
                return {
                    "success": False,
                    "exit_code": exit_code,
                    "output": None,
                    "error": f"Failed to parse output: {e}",
                    "error_type": "OutputParseError",
                    "stack_trace": stderr_str[:1000],
                }
            
        finally:
            try:
                os.unlink(temp_script)
            except FileNotFoundError:
                pass
    
    def _execute_in_namespace(
        self,
        code: str,
        context: IsolationContext,
        timeout: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute code in Linux namespaces."""
        if os.name != 'posix':
            # Fall back to process isolation on non-Unix systems
            return self._execute_in_process(code, context, timeout, max_memory_mb)
        
        # Check if unshare is available
        try:
            subprocess.run(['unshare', '--help'], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            return self._execute_in_process(code, context, timeout, max_memory_mb)
        
        timeout = timeout or self.config.timeout
        max_memory_mb = max_memory_mb or self.config.max_memory_mb
        
        # Build unshare command
        unshare_flags = context.namespaces.to_unshare_flags() if context.namespaces else []
        
        # Create wrapper script
        wrapper = self._build_namespace_wrapper(code, context)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(wrapper)
            temp_script = f.name
        
        try:
            cmd = ['unshare'] + unshare_flags + [sys.executable, temp_script]
            
            env = context.env or os.environ.copy()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                env=env,
                cwd=str(context.work_dir) if context.work_dir else None,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                return {
                    "success": False,
                    "exit_code": 124,
                    "output": None,
                    "error": "Execution timed out in namespace",
                }
            
            try:
                output_str = stdout.decode('utf-8')
                return json.loads(output_str)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {
                    "success": False,
                    "exit_code": process.returncode or 1,
                    "output": None,
                    "error": stderr.decode('utf-8', errors='replace')[:500],
                }
            
        finally:
            try:
                os.unlink(temp_script)
            except FileNotFoundError:
                pass
    
    def _build_process_wrapper(
        self,
        code: str,
        isolation_id: str,
        temp_dir: str,
        work_dir: str,
    ) -> str:
        """Build wrapper script for process isolation."""
        import json
        
        return f'''
import sys
import os
import traceback
import time

# Setup isolation
execution_id = "{isolation_id}"
temp_dir = "{temp_dir}" if "{temp_dir}" else None
work_dir = "{work_dir}" if "{work_dir}" else None

# Change to work directory if available
if work_dir and os.path.exists(work_dir):
    os.chdir(work_dir)

# Execute user code
result = None
output_type = "none"
success = False
error = None
error_type = None
stack_trace = None

start_time = time.time()

try:
    {code}
    success = True
    output_type = type(result).__name__
except SystemExit as e:
    success = False
    error = str(e)
    error_type = "SystemExit"
except Exception as e:
    success = False
    error = str(e)
    error_type = type(e).__name__
    stack_trace = traceback.format_exc()

end_time = time.time()

output = {{
    "success": success,
    "exit_code": 0 if success else 1,
    "output": result,
    "output_type": output_type,
    "error": error,
    "error_type": error_type,
    "stack_trace": stack_trace,
    "execution_time": end_time - start_time,
}}

print({json.dumps(output, default=str)})
'''
    
    def _build_namespace_wrapper(self, code: str, context: IsolationContext) -> str:
        """Build wrapper script for namespace isolation."""
        import json
        
        return f'''
import sys
import os
import json
import traceback
import time

# Setup namespace isolation
execution_id = "{context.isolation_id}"
temp_dir = "{context.temp_dir}" if {bool(context.temp_dir)} else None
work_dir = "{context.work_dir}" if {bool(context.work_dir)} else None

# Change to work directory
if work_dir and os.path.exists(work_dir):
    os.chdir(work_dir)

# Note: In namespace mode, we're already isolated by unshare
# This code runs inside the isolated environment

result = None
output_type = "none"
success = False
error = None
error_type = None
stack_trace = None

start_time = time.time()

try:
    {code}
    success = True
    output_type = type(result).__name__
except SystemExit as e:
    success = False
    error = str(e)
    error_type = "SystemExit"
except Exception as e:
    success = False
    error = str(e)
    error_type = type(e).__name__
    stack_trace = traceback.format_exc()

end_time = time.time()

output = {{
    "success": success,
    "exit_code": 0 if success else 1,
    "output": result,
    "output_type": output_type,
    "error": error,
    "error_type": error_type,
    "stack_trace": stack_trace,
    "execution_time": end_time - start_time,
    "isolation_id": "{context.isolation_id}",
    "isolation_mode": "namespace",
}}

print(json.dumps(output, default=str))
'''


# =============================================================================
# Chroot Isolation (Unix only, requires root)
# =============================================================================

class ChrootIsolationManager:
    """
    Manages chroot-based isolation (requires root privileges).
    
    Note: This is experimental and requires proper setup of the chroot environment.
    """
    
    def __init__(self, chroot_dir: str = "/var/sandbox"):
        """
        Initialize chroot isolation manager.
        
        Args:
            chroot_dir: Directory to use as chroot
        """
        self.chroot_dir = Path(chroot_dir)
    
    def setup_chroot(self) -> None:
        """
        Set up a basic chroot environment.
        
        This creates the necessary directories and copies essential files.
        Note: Requires root privileges.
        """
        if os.geteuid() != 0:
            raise PermissionError("setup_chroot requires root privileges")
        
        # Create chroot directory structure
        dirs = [
            'bin', 'dev', 'etc', 'home', 'lib', 'lib64',
            'proc', 'sys', 'tmp', 'usr', 'usr/bin', 'usr/lib'
        ]
        
        for d in dirs:
            (self.chroot_dir / d).mkdir(parents=True, exist_ok=True)
        
        # Copy essential binaries
        essential_binaries = ['/bin/bash', '/bin/sh', '/usr/bin/python3']
        for binary in essential_binaries:
            if Path(binary).exists():
                target = self.chroot_dir / binary.lstrip('/')
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    import shutil
                    shutil.copy2(binary, target)
                except Exception as e:
                    print(f"Warning: Failed to copy {binary}: {e}")
        
        # Mount essential filesystems
        mounts = [
            ('/proc', 'proc'),
            ('/dev', 'dev'),
            ('/sys', 'sys'),
        ]
        
        for source, target in mounts:
            target_path = self.chroot_dir / target
            if not target_path.exists():
                target_path.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.run(['mount', '--bind', source, target_path], check=True)
            except Exception:
                pass  # Ignore mount failures
    
    def cleanup_chroot(self) -> None:
        """Clean up chroot environment."""
        # Unmount filesystems
        mounts = ['proc', 'dev', 'sys']
        for target in mounts:
            target_path = self.chroot_dir / target
            try:
                subprocess.run(['umount', target_path], check=False)
            except Exception:
                pass
    
    def execute_in_chroot(
        self,
        code: str,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Execute code in a chroot environment.
        
        Args:
            code: Python code to execute
            timeout: Timeout in seconds
            
        Returns:
            Dict with execution results
        """
        if os.geteuid() != 0:
            raise PermissionError("execute_in_chroot requires root privileges")
        
        # Write code to temp file inside chroot
        code_file = self.chroot_dir / f"tmp/code_{uuid.uuid4().hex}.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text(code)
        
        try:
            # Execute in chroot
            cmd = [
                'chroot',
                str(self.chroot_dir),
                '/usr/bin/python3',
                str(code_file),
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                return {
                    "success": False,
                    "error": "Chroot execution timed out",
                }
            
            return {
                "success": process.returncode == 0,
                "output": stdout.decode('utf-8'),
                "error": stderr.decode('utf-8') if process.returncode != 0 else None,
            }
            
        finally:
            try:
                code_file.unlink()
            except FileNotFoundError:
                pass


# =============================================================================
# Container Isolation (Future)
# =============================================================================

class ContainerIsolationManager:
    """
    Manages container-based isolation (Docker, Podman, etc.).
    
    Note: This is a placeholder for future implementation.
    """
    
    def __init__(self, container_runtime: str = "docker"):
        self.container_runtime = container_runtime
    
    def execute_in_container(
        self,
        code: str,
        image: str = "python:3.11-slim",
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Execute code in a container.
        
        Note: This is a placeholder. Actual implementation would use
        Docker SDK or subprocess to run containers.
        """
        raise NotImplementedError("Container isolation not yet implemented")


# =============================================================================
# Utility Functions
# =============================================================================

def get_isolation_manager(mode: Optional[IsolationMode] = None) -> IsolationManager:
    """Get an isolation manager with the specified mode."""
    if mode is None:
        # Default to process isolation
        mode = IsolationMode.PROCESS
    return IsolationManager()


def execute_isolated(
    code: str,
    mode: IsolationMode = IsolationMode.PROCESS,
    timeout: Optional[float] = None,
    max_memory_mb: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Execute code in isolation.
    
    Convenience function for one-off isolated execution.
    """
    manager = get_isolation_manager(mode)
    return manager.execute_in_context(
        code=code,
        mode=mode,
        timeout=timeout,
        max_memory_mb=max_memory_mb,
    )
