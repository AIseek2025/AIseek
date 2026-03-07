"""
Logger System (Refactored from Fusion)
Structured logging with job context support.
"""

import logging
import sys
from typing import Any, Optional
from pathlib import Path

# Default Log Format
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    format_str: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT
) -> None:
    """
    Initialize the logging system.
    """
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    
    log_level = level_map.get(level.lower(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(format_str, date_format)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler (if provided)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set levels for third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    
    logging.info("Logging system initialized. Level: %s", level.upper())


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def log_job(
    logger: logging.Logger,
    job_id: str,
    message: str,
    level: str = "info",
    **kwargs: Any
) -> None:
    """
    Log a message with job context.
    """
    extra_parts = []
    for key, value in kwargs.items():
        if value is not None:
            extra_parts.append(f"{key}={value}")
    
    extra_str = " ".join(extra_parts)
    full_message = f"job_id={job_id} {message}"
    if extra_str:
        full_message += f" {extra_str}"
    
    level_method = getattr(logger, level.lower(), logger.info)
    level_method(full_message)


class JobLogger:
    """Wrapper for job-specific logging."""
    
    def __init__(self, logger: logging.Logger, job_id: str):
        self.logger = logger
        self.job_id = job_id
    
    def debug(self, message: str, **kwargs):
        log_job(self.logger, self.job_id, message, "debug", **kwargs)
    
    def info(self, message: str, **kwargs):
        log_job(self.logger, self.job_id, message, "info", **kwargs)
    
    def warning(self, message: str, **kwargs):
        log_job(self.logger, self.job_id, message, "warning", **kwargs)
    
    def error(self, message: str, **kwargs):
        log_job(self.logger, self.job_id, message, "error", **kwargs)
    
    def critical(self, message: str, **kwargs):
        log_job(self.logger, self.job_id, message, "critical", **kwargs)
    
    def start(self, **kwargs):
        self.info("start", **kwargs)
    
    def processing(self, **kwargs):
        self.info("processing", **kwargs)
    
    def done(self, **kwargs):
        self.info("done", **kwargs)
    
    def error_occurred(self, error: Exception, **kwargs):
        self.error("error", error=str(error), **kwargs)
