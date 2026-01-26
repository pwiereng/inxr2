"""Tests for logging configuration."""

import logging

import pytest

from inxr2.infrastructure.logging import configure_logging


class TestConfigureLogging:
    """Tests for configure_logging function.

    Note: These tests verify the configure_logging function behavior in isolation.
    When running under pytest, the logging system may already be configured,
    so we test by examining what the function does rather than the global state.
    """

    def test_configure_logging_does_not_raise(self) -> None:
        """configure_logging should not raise any errors."""
        # Should execute without errors
        configure_logging()

    def test_configure_logging_idempotent(self) -> None:
        """configure_logging can be called multiple times safely."""
        # Should not raise any errors when called multiple times
        configure_logging()
        configure_logging()
        configure_logging()

    def test_configure_logging_uses_basic_config(self) -> None:
        """configure_logging should use logging.basicConfig internally."""
        # Verify the function exists and is callable
        assert callable(configure_logging)

        # The function should complete without errors
        try:
            configure_logging()
        except Exception as e:
            pytest.fail(f"configure_logging raised an exception: {e}")

    def test_module_logger_can_log(self) -> None:
        """Module loggers should work after configure_logging."""
        configure_logging()

        # Create a module logger
        module_logger = logging.getLogger("test.module.infrastructure")

        # Should be able to log without errors
        # (actual output depends on test runner configuration)
        module_logger.debug("Debug message")
        module_logger.info("Info message")
        module_logger.warning("Warning message")
        module_logger.error("Error message")

    def test_configure_logging_calls_basic_config_correctly(self) -> None:
        """configure_logging should call basicConfig with INFO level and stdout handler."""
        import sys
        from unittest.mock import patch

        with patch("logging.basicConfig") as mock_basic_config:
            # Import fresh to ensure we test the actual call
            import importlib

            import inxr2.infrastructure.logging as log_module

            importlib.reload(log_module)
            log_module.configure_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Get the call arguments
            call_kwargs = mock_basic_config.call_args[1]

            # Verify INFO level
            assert call_kwargs["level"] == logging.INFO

            # Verify format string contains key components
            format_str = call_kwargs["format"]
            assert "%(asctime)s" in format_str
            assert "%(name)s" in format_str
            assert "%(levelname)s" in format_str
            assert "%(message)s" in format_str

            # Verify handlers includes a StreamHandler to stdout
            handlers = call_kwargs["handlers"]
            assert len(handlers) == 1
            handler = handlers[0]
            assert isinstance(handler, logging.StreamHandler)
            assert handler.stream is sys.stdout
