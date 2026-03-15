"""Tests for FileFilter domain service."""

import pytest

from inxr2.domain.services.file_filter import FileFilter


class TestFileFilterPathSkip:
    """Tests for path-based skip heuristics."""

    @pytest.mark.parametrize(
        "path",
        [
            "lib/jquery.min.js",
            "assets/styles.min.css",
            "js/app.min.mjs",
            "vendor/lodash.js",
            "node_modules/express/index.js",
            "dist/bundle.js",
            "build/output.js",
            "third_party/lib.js",
            "3rdparty/plugin.js",
            "bower_components/angular/angular.js",
            "src/vendor/chart.js",
            "deep/nested/node_modules/pkg/index.js",
            "static/app.bundle.js",
            "css/main.bundle.css",
            # Bundler hash pattern
            "static/app.a1b2c3d4.js",
            "assets/main.deadbeef.css",
            "js/chunk.0123456789ab.mjs",
        ],
    )
    def test_skips_vendor_and_minified_files(self, path: str) -> None:
        assert FileFilter.should_skip(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/main.py",
            "src/utils.ts",
            "lib/helpers.js",
            "src/components/App.tsx",
            "README.md",
            "tests/test_main.py",
            "src/vendor.py",  # "vendor" as filename, not directory
            "src/build_utils.py",  # "build" as prefix, not directory
            "dist.py",  # "dist" as filename, not directory
            "src/inxr2/adapters/external/treesitter/python_parser.py",  # first-party code
            "external/dep.js",  # "external" alone is not a reliable vendor signal
            "src/main.js",
            "frontend/src/App.js",
            "assets/app.20240101.js",  # date stamp, not bundler hash
            "static/data.12345678.css",  # purely numeric, not hex hash
        ],
    )
    def test_does_not_skip_normal_files(self, path: str) -> None:
        assert FileFilter.should_skip(path) is False

    def test_case_insensitive_minified_suffix(self) -> None:
        assert FileFilter.should_skip("lib/jQuery.MIN.JS") is True

    def test_case_insensitive_directory(self) -> None:
        assert FileFilter.should_skip("Node_Modules/pkg/index.js") is True

    def test_backslash_path_separator(self) -> None:
        assert FileFilter.should_skip("node_modules\\express\\index.js") is True

    def test_external_directory_not_skipped(self) -> None:
        # Regression test for issue #349: "external" was incorrectly in
        # _SKIP_DIRECTORIES, causing all files under src/.../external/ to be
        # silently dropped during indexing.
        assert (
            FileFilter.should_skip(
                "src/inxr2/adapters/external/treesitter/python_parser.py"
            )
            is False
        )
        assert FileFilter.should_skip("external/dep.js") is False
        assert FileFilter.should_skip("lib/external/utils.py") is False
