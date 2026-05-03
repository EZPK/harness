"""
Logging configuration for Harness Agentic Framework.

This module configures Python logging to:
- Write logs to a file (harness.log)
- NOT send logs to chat/output
- Provide structured logging for debugging
"""

import logging
import sys
from pathlib import Path
from typing import Optional


# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Main log file
MAIN_LOG_FILE = LOGS_DIR / "harness.log"

# Error log file
ERROR_LOG_FILE = LOGS_DIR / "harness_errors.log"


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    enable_console: bool = False,
) -> None:
    """
    Configure logging for the Harness framework.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (defaults to logs/harness.log)
        enable_console: If True, also log to console (stderr)
    
    This will:
    - Remove any existing handlers from root logger
    - Add file handler for persistent logs
    - Optionally add console handler
    - Suppress Textual internal logs in chat
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set level
    root_logger.setLevel(level)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    log_path = Path(log_file) if log_file else MAIN_LOG_FILE
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (only errors)
    error_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s\n%(exc_text)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler = logging.FileHandler(ERROR_LOG_FILE, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_handler)
    
    # Console handler (optional)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Suppress noisy third-party loggers
    _suppress_noisy_loggers()
    
    # Log startup
    logging.info(f"Logging configured: level={logging.getLevelName(level)}, file={log_path}")


def _suppress_noisy_loggers() -> None:
    """Suppress verbose logging from third-party libraries."""
    noisy_loggers = [
        'httpcore',
        'httpx',
        'http.client',
        'urllib3',
        'asyncio',
        'textual',
        'rich',
        'markdown',
        'aiohttp',
        'aiosqlite',
        'litellm',
        'openai',
        'requests',
    ]
    
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
            logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """Log an exception with full traceback."""
    logger.error(f"{message}\n{exc}", exc_info=True)


# Initialize logging on import
setup_logging(level=logging.INFO, enable_console=False)
