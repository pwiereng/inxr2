"""Logging configuration."""

import logging
import sys


def configure_logging() -> None:
    """
    Configure application logging.

    TODO: Add structured logging
    TODO: Add log rotation
    TODO: Add different log levels for different modules
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
