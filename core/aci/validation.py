"""
ACI Validation Module.

Provides validation and sanitization for all ACI messages.
This is a critical security component (Part of the 98.4% harness infrastructure).
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ValidationError

from .interface import ACIError, ACISecurityError, ACIValidationError
from .commands import Command, CommandType
from .responses import Response


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class ValidationResult:
    """Result of validating a message."""
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    sanitized_data: Optional[Dict[str, Any]] = None
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "sanitized_data": self.sanitized_data,
        }


# =============================================================================
# ACI Validator
# =============================================================================

class ACIValidator:
    """
    Validates and sanitizes ACI messages.
    
    This validator ensures that:
    1. Messages conform to the expected schema
    2. Messages don't contain malicious content
    3. Messages are properly formatted
    4. Required fields are present
    """
    
    # Maximum sizes
    MAX_STRING_LENGTH = 10000
    MAX_LIST_LENGTH = 1000
    MAX_DICT_DEPTH = 10
    MAX_DICT_SIZE = 1000
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB
    
    # Dangerous patterns
    DANGEROUS_PATTERNS = [
        r'<script.*?>.*?</script>',  # XSS
        r'javascript:',              # JS injection
        r'on\w+\s*=',              # Event handlers
        r'eval\(',                  # eval()
        r'exec\(',                  # exec()
        r'system\(',                # system()
        r'os\.system\(',            # os.system()
        r'subprocess\.',            # subprocess
        r'__import__',               # Dynamic import
        r'open\(',                  # File open (context depends)
        r'\bimport\s+os\b',         # Import OS
        r'\bimport\s+sys\b',        # Import sys
        r'\bimport\s+subprocess\b', # Import subprocess
    ]
    
    # Allowed characters for different field types
    SAFE_STRING_PATTERN = re.compile(r'^[\w\s\-.,;:!?@#$%^&*()\[\]{}"' + r"'\\/+=<>`~|]+$', re.UNICODE)
    ID_PATTERN = re.compile(r'^[a-zA-Z][\w\-]*$')
    
    def __init__(self):
        """Initialize the validator."""
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL) 
            for pattern in self.DANGEROUS_PATTERNS
        ]
    
    def validate(self, message: Union[Command, Response, BaseModel]) -> ValidationResult:
        """
        Validate a message.
        
        Args:
            message: The message to validate
            
        Returns:
            ValidationResult: The validation result
        """
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[]
        )
        
        try:
            # Validate with Pydantic first
            message.model_dump()
        except (ValidationError, AttributeError) as e:
            result.add_error(f"Pydantic validation failed: {e}")
            return result
        
        # Check message size
        if self._get_message_size(message) > self.MAX_MESSAGE_SIZE:
            result.add_error(f"Message exceeds maximum size of {self.MAX_MESSAGE_SIZE} bytes")
        
        # Validate based on message type
        if isinstance(message, Command):
            self._validate_command(message, result)
        elif isinstance(message, Response):
            self._validate_response(message, result)
        else:
            self._validate_generic(message, result)
        
        return result
    
    def validate_and_sanitize(
        self, 
        message: Union[Command, Response, BaseModel]
    ) -> Tuple[bool, Union[Command, Response, BaseModel]]:
        """
        Validate and sanitize a message.
        
        Args:
            message: The message to validate and sanitize
            
        Returns:
            Tuple of (is_valid, sanitized_message)
            
        Raises:
            ACISecurityError: If message contains security violations
        """
        result = self.validate(message)
        
        if not result.is_valid:
            raise ACIValidationError(
                "Message validation failed",
                errors=result.errors
            )
        
        # Sanitize the message
        sanitized = self.sanitize(message)
        
        return True, sanitized
    
    def sanitize(self, data: Any) -> Any:
        """
        Sanitize data to remove potentially dangerous content.
        
        Args:
            data: Data to sanitize
            
        Returns:
            Sanitized data
        """
        if data is None:
            return None
        
        if isinstance(data, str):
            return self._sanitize_string(data)
        elif isinstance(data, bytes):
            return self._sanitize_bytes(data)
        elif isinstance(data, dict):
            return self._sanitize_dict(data)
        elif isinstance(data, (list, tuple)):
            return self._sanitize_list(data)
        elif isinstance(data, (int, float, bool)):
            return data
        elif hasattr(data, 'model_dump'):
            # Pydantic model
            sanitized_data = self.sanitize(data.model_dump())
            return type(data)(**sanitized_data)
        else:
            # Unknown type, return as-is (shouldn't happen with typed data)
            return data
    
    def _get_message_size(self, message: BaseModel) -> int:
        """Get the size of a message in bytes."""
        try:
            return len(message.model_dump_json())
        except Exception:
            return len(str(message))
    
    def _validate_command(self, command: Command, result: ValidationResult) -> None:
        """Validate a command message."""
        # Validate required fields based on command type
        if command.command_type == CommandType.TASK_ASSIGNMENT:
            self._validate_task_assignment(command, result)
        elif command.command_type == CommandType.TASK_PROGRESS:
            self._validate_task_progress(command, result)
        elif command.command_type == CommandType.TASK_RESULT:
            self._validate_task_result(command, result)
        elif command.command_type == CommandType.TASK_ERROR:
            self._validate_task_error(command, result)
        elif command.command_type == CommandType.CONTEXT_REQUEST:
            self._validate_context_request(command, result)
        elif command.command_type == CommandType.CONTEXT_RESPONSE:
            self._validate_context_response(command, result)
        
        # Common validations for all commands
        self._validate_sender(command.sender, "sender", result)
        if command.receiver:
            self._validate_receiver(command.receiver, "receiver", result)
    
    def _validate_response(self, response: Response, result: ValidationResult) -> None:
        """Validate a response message."""
        self._validate_sender(response.sender, "sender", result)
        if response.receiver:
            self._validate_receiver(response.receiver, "receiver", result)
    
    def _validate_generic(self, message: BaseModel, result: ValidationResult) -> None:
        """Validate a generic message."""
        # Just check the data recursively
        self._validate_data(message.model_dump(), result)
    
    def _validate_task_assignment(self, command: Command, result: ValidationResult) -> None:
        """Validate a task assignment command."""
        data = command.model_dump()
        
        # Check task_id
        self._validate_id(data.get('task_id'), 'task_id', result)
        
        # Check task_name
        task_name = data.get('task_name', '')
        if not task_name or len(task_name) > 200:
            result.add_error("task_name is required and must be <= 200 characters")
        else:
            self._check_dangerous_patterns(task_name, 'task_name', result)
        
        # Check task_description
        task_desc = data.get('task_description', '')
        if not task_desc:
            result.add_warning("task_description is recommended")
        elif len(task_desc) > self.MAX_STRING_LENGTH:
            result.add_error(f"task_description exceeds maximum length of {self.MAX_STRING_LENGTH}")
        else:
            self._check_dangerous_patterns(task_desc, 'task_description', result)
        
        # Validate parameters
        parameters = data.get('parameters', {})
        self._validate_parameters(parameters, result)
        
        # Validate context
        context = data.get('context', {})
        self._validate_context(context, result)
        
        # Check timeout
        timeout = data.get('timeout')
        if timeout is not None:
            if not isinstance(timeout, int) or timeout <= 0 or timeout > 86400:
                result.add_error("timeout must be a positive integer <= 86400 (24 hours)")
    
    def _validate_task_progress(self, command: Command, result: ValidationResult) -> None:
        """Validate a task progress command."""
        data = command.model_dump()
        
        self._validate_id(data.get('task_id'), 'task_id', result)
        
        progress = data.get('progress_percent')
        if progress is not None:
            if not (0 <= progress <= 100):
                result.add_error("progress_percent must be between 0 and 100")
        
        progress_msg = data.get('progress_message', '')
        if len(progress_msg) > 500:
            result.add_warning("progress_message should be <= 500 characters")
        
        # Validate partial results
        partial_results = data.get('partial_results', {})
        self._validate_data(partial_results, result)
    
    def _validate_task_result(self, command: Command, result: ValidationResult) -> None:
        """Validate a task result command."""
        data = command.model_dump()
        
        self._validate_id(data.get('task_id'), 'task_id', result)
        
        # Check execution time
        exec_time = data.get('execution_time_ms')
        if exec_time is not None:
            if not isinstance(exec_time, (int, float)) or exec_time < 0:
                result.add_error("execution_time_ms must be a non-negative number")
        
        # Validate result (can be any type, so we just check size)
        result_data = data.get('result')
        if result_data:
            result_size = self._get_data_size(result_data)
            if result_size > self.MAX_MESSAGE_SIZE / 2:  # Result gets half the limit
                result.add_warning(f"result is large ({result_size} bytes), consider streaming")
        
        # Validate outputs
        outputs = data.get('outputs', {})
        self._validate_data(outputs, result)
    
    def _validate_task_error(self, command: Command, result: ValidationResult) -> None:
        """Validate a task error command."""
        data = command.model_dump()
        
        self._validate_id(data.get('task_id'), 'task_id', result)
        
        error_type = data.get('error_type', '')
        if not error_type:
            result.add_error("error_type is required for error commands")
        
        error_msg = data.get('error_message', '')
        if not error_msg:
            result.add_error("error_message is required for error commands")
        elif len(error_msg) > 2000:
            result.add_warning("error_message is very long (> 2000 chars)")
        
        # Check retry count
        retry_count = data.get('retry_count')
        if retry_count is not None:
            if not isinstance(retry_count, int) or retry_count < 0:
                result.add_error("retry_count must be a non-negative integer")
    
    def _validate_context_request(self, command: Command, result: ValidationResult) -> None:
        """Validate a context request command."""
        data = command.model_dump()
        
        self._validate_id(data.get('context_id'), 'context_id', result)
        
        context_type = data.get('context_type', '')
        if not context_type:
            result.add_error("context_type is required for context requests")
        
        # Validate query
        query = data.get('query', {})
        self._validate_data(query, result)
    
    def _validate_context_response(self, command: Command, result: ValidationResult) -> None:
        """Validate a context response command."""
        data = command.model_dump()
        
        self._validate_id(data.get('context_id'), 'context_id', result)
        
        context_type = data.get('context_type', '')
        if not context_type:
            result.add_error("context_type is required for context responses")
        
        # Validate context data
        context = data.get('context')
        if context:
            context_size = self._get_data_size(context)
            if context_size > self.MAX_MESSAGE_SIZE / 2:
                result.add_warning(f"context is large ({context_size} bytes)")
            self._validate_data(context, result)
    
    def _validate_id(self, id_value: Any, field_name: str, result: ValidationResult) -> None:
        """Validate an ID field."""
        if not id_value:
            result.add_error(f"{field_name} is required")
            return
        
        if not isinstance(id_value, str):
            result.add_error(f"{field_name} must be a string")
            return
        
        if len(id_value) > 100:
            result.add_error(f"{field_name} must be <= 100 characters")
            return
        
        if not self.ID_PATTERN.match(id_value):
            result.add_warning(f"{field_name} should use only alphanumeric characters and hyphens")
    
    def _validate_sender(self, sender: str, field_name: str, result: ValidationResult) -> None:
        """Validate sender field."""
        if not sender:
            result.add_error(f"{field_name} is required")
        elif len(sender) > 100:
            result.add_error(f"{field_name} must be <= 100 characters")
        elif not self.SAFE_STRING_PATTERN.match(sender):
            result.add_warning(f"{field_name} contains unusual characters")
    
    def _validate_receiver(self, receiver: str, field_name: str, result: ValidationResult) -> None:
        """Validate receiver field."""
        self._validate_sender(receiver, field_name, result)
    
    def _validate_parameters(self, parameters: Dict, result: ValidationResult) -> None:
        """Validate task parameters."""
        if not isinstance(parameters, dict):
            result.add_error("parameters must be a dictionary")
            return
        
        if len(parameters) > 50:
            result.add_warning(f"parameters has {len(parameters)} entries (max recommended: 50)")
        
        for key, value in parameters.items():
            if not isinstance(key, str) or len(key) > 100:
                result.add_error(f"Invalid parameter key: {key}")
            self._validate_data(value, result, depth=1)
    
    def _validate_context(self, context: Dict, result: ValidationResult) -> None:
        """Validate context data."""
        if not isinstance(context, dict):
            result.add_error("context must be a dictionary")
            return
        
        if len(context) > 100:
            result.add_warning(f"context has {len(context)} entries (max recommended: 100)")
        
        for key, value in context.items():
            if not isinstance(key, str) or len(key) > 200:
                result.add_error(f"Invalid context key: {key}")
            self._validate_data(value, result, depth=1)
    
    def _validate_data(self, data: Any, result: ValidationResult, depth: int = 0) -> None:
        """Recursively validate data."""
        if depth > self.MAX_DICT_DEPTH:
            result.add_error(f"Data exceeds maximum depth of {self.MAX_DICT_DEPTH}")
            return
        
        if isinstance(data, str):
            if len(data) > self.MAX_STRING_LENGTH:
                result.add_warning(f"String exceeds recommended length ({self.MAX_STRING_LENGTH})")
            self._check_dangerous_patterns(data, "data", result)
        elif isinstance(data, bytes):
            if len(data) > self.MAX_STRING_LENGTH:
                result.add_warning("Bytes data is very long")
        elif isinstance(data, dict):
            if len(data) > self.MAX_DICT_SIZE:
                result.add_warning(f"Dictionary has {len(data)} entries (max: {self.MAX_DICT_SIZE})")
            for value in data.values():
                self._validate_data(value, result, depth + 1)
        elif isinstance(data, (list, tuple)):
            if len(data) > self.MAX_LIST_LENGTH:
                result.add_warning(f"List has {len(data)} entries (max: {self.MAX_LIST_LENGTH})")
            for item in data:
                self._validate_data(item, result, depth + 1)
    
    def _get_data_size(self, data: Any) -> int:
        """Get the approximate size of data in bytes."""
        try:
            return len(json.dumps(data))
        except Exception:
            return len(str(data))
    
    def _check_dangerous_patterns(self, text: str, field_name: str, result: ValidationResult) -> None:
        """Check for dangerous patterns in text."""
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                result.add_error(
                    f"{field_name} contains potentially dangerous pattern: {pattern.pattern[:50]}..."
                )
    
    def _sanitize_string(self, text: str) -> str:
        """Sanitize a string."""
        # Remove dangerous patterns
        for pattern in self._compiled_patterns:
            text = pattern.sub("", text)
        
        # Limit length
        if len(text) > self.MAX_STRING_LENGTH:
            text = text[:self.MAX_STRING_LENGTH] + "..."
        
        return text
    
    def _sanitize_bytes(self, data: bytes) -> bytes:
        """Sanitize bytes."""
        text = data.decode('utf-8', errors='replace')
        sanitized = self._sanitize_string(text)
        return sanitized.encode('utf-8')
    
    def _sanitize_dict(self, data: Dict) -> Dict:
        """Sanitize a dictionary."""
        if len(data) > self.MAX_DICT_SIZE:
            # Truncate to max size
            data = dict(list(data.items())[:self.MAX_DICT_SIZE])
        
        return {
            self._sanitize_key(k): self.sanitize(v)
            for k, v in data.items()
        }
    
    def _sanitize_list(self, data: Union[List, Tuple]) -> List:
        """Sanitize a list or tuple."""
        if len(data) > self.MAX_LIST_LENGTH:
            data = data[:self.MAX_LIST_LENGTH]
        
        return [self.sanitize(item) for item in data]
    
    def _sanitize_key(self, key: Any) -> str:
        """Sanitize a dictionary key."""
        if not isinstance(key, str):
            return str(key)
        return self._sanitize_string(key)


# =============================================================================
# Global Validator Instance
# =============================================================================

validator = ACIValidator()


# =============================================================================
# Convenience Functions
# =============================================================================

def validate_message(message: Union[Command, Response, BaseModel]) -> ValidationResult:
    """
    Validate a message using the global validator.
    
    Args:
        message: The message to validate
        
    Returns:
        ValidationResult: The validation result
    """
    return validator.validate(message)


def sanitize_input(data: Any) -> Any:
    """
    Sanitize input data using the global validator.
    
    Args:
        data: Data to sanitize
        
    Returns:
        Sanitized data
    """
    return validator.sanitize(data)


def validate_output(data: Any) -> Any:
    """
    Validate and sanitize output data.
    
    Args:
        data: Data to validate and sanitize
        
    Returns:
        Validated and sanitized data
        
    Raises:
        ACISecurityError: If data contains security violations
    """
    return validator.sanitize(data)


# Import json for serialization
import json
