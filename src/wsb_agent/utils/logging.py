"""Structured logging setup for WSB Agent."""

from __future__ import annotations

import logging
import sys
from typing import Literal


class ColorFormatter(logging.Formatter):
    """Custom formatter to add colors to terminal output."""
    
    # ANSI escape sequences for colors
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    
    def format(self, record):
        original_msg = super().format(record)
        if record.levelno == logging.WARNING:
            return f"{self.YELLOW}{original_msg}{self.RESET}"
        elif record.levelno >= logging.ERROR:
            return f"{self.RED}{original_msg}{self.RESET}"
        return original_msg

def setup_logging(
    level: str = "INFO",
    log_format: Literal["text", "json"] = "text",
) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format - "text" for human-readable, "json" for structured.

    Returns:
        Configured root logger for wsb_agent.
    """
    logger = logging.getLogger("wsb_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates on re-init
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if log_format == "json":
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"module": "%(name)s", "message": "%(message)s"}'
        )
    else:
        formatter = ColorFormatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the wsb_agent namespace.

    Args:
        name: Logger name (will be prefixed with 'wsb_agent.').

    Returns:
        Logger instance.
    """
    return logging.getLogger(f"wsb_agent.{name}")
