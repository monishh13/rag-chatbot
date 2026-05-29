"""
Structured logging configuration.
Logs to both console and file with timestamps and context.
"""

import logging
import os
from app.core.config import get_settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    settings = get_settings()

    # Ensure log directory exists
    log_dir = os.path.dirname(settings.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger("rag_chatbot")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Prevent duplicate handlers on re-initialization
    if logger.handlers:
        return logger

    # Log format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    try:
        file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not create log file: {e}")

    return logger


def get_logger() -> logging.Logger:
    """Get the application logger."""
    logger = logging.getLogger("rag_chatbot")
    if not logger.handlers:
        return setup_logging()
    return logger
