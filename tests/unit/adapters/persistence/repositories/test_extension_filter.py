"""Tests for the split_extension_filter helper."""

from inxr2.adapters.persistence.repositories.query_utils import split_extension_filter


class TestSplitExtensionFilter:
    def test_only_real_extensions(self) -> None:
        real_exts, has_none = split_extension_filter([".py", ".js"])
        assert real_exts == [".py", ".js"]
        assert has_none is False

    def test_only_none_sentinel(self) -> None:
        real_exts, has_none = split_extension_filter(["(none)"])
        assert real_exts == []
        assert has_none is True

    def test_mixed_extensions_and_none(self) -> None:
        real_exts, has_none = split_extension_filter([".py", "(none)", ".js"])
        assert real_exts == [".py", ".js"]
        assert has_none is True

    def test_empty_list(self) -> None:
        real_exts, has_none = split_extension_filter([])
        assert real_exts == []
        assert has_none is False

    def test_preserves_order(self) -> None:
        real_exts, _ = split_extension_filter([".ts", ".go", ".rb"])
        assert real_exts == [".ts", ".go", ".rb"]
