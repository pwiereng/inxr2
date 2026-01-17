"""CLI adapters - command-line interface."""

from .commands import (
    run_full_index,
    run_incremental_index,
    show_index_status,
    show_overall_status,
)

__all__ = [
    "run_full_index",
    "run_incremental_index",
    "show_index_status",
    "show_overall_status",
]
