"""Logging configuration for the application."""

import logging
import sys

from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    
    # Create logger
    logger = logging.getLogger("patshal")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler with detailed formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Detailed format for debug mode
    if settings.DEBUG:
        formatter = logging.Formatter(
            "\n%(levelname)s [%(asctime)s] %(name)s\n"
            "└── %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        formatter = logging.Formatter(
            "%(levelname)s: %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Application logger instance
logger = setup_logging()

