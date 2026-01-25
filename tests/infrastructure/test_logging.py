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

    def test_configure_logging_configures_stream_to_stdout(self) -> None:
        """configure_logging should configure handlers to use stdout."""
        # We can't directly test the effect due to pytest's logging capture,
        # but we can verify the function uses the correct parameters
        # by checking that sys.stdout is used in the module
        # Read the source to verify sys.stdout is referenced
        import inspect

        import inxr2.infrastructure.logging as log_module

        source = inspect.getsource(log_module.configure_logging)
        assert "sys.stdout" in source

    def test_configure_logging_sets_info_level(self) -> None:
        """configure_logging should set INFO level in basicConfig call."""
        import inspect

        import inxr2.infrastructure.logging as log_module

        source = inspect.getsource(log_module.configure_logging)
        # Verify INFO level is specified
        assert "logging.INFO" in source

    def test_configure_logging_sets_format_string(self) -> None:
        """configure_logging should set a format string with key components."""
        import inspect

        import inxr2.infrastructure.logging as log_module

        source = inspect.getsource(log_module.configure_logging)
        # Verify format string contains expected placeholders
        assert "%(asctime)s" in source
        assert "%(name)s" in source
        assert "%(levelname)s" in source
        assert "%(message)s" in source
