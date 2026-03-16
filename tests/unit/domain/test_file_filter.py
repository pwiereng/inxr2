"""Tests for FileFilter domain service."""

import pytest

from inxr2.domain.services.file_filter import FileFilter


class TestFileFilterMinifiedAndBundled:
    """Tests for minified/bundled file skip heuristics (always active)."""

    @pytest.mark.parametrize(
        "path",
        [
            "lib/jquery.min.js",
            "assets/styles.min.css",
            "js/app.min.mjs",
            "static/app.bundle.js",
            "css/main.bundle.css",
            # Bundler hash pattern
            "static/app.a1b2c3d4.js",
            "assets/main.deadbeef.css",
            "js/chunk.0123456789ab.mjs",
        ],
    )
    def test_skips_minified_and_bundled_files(self, path: str) -> None:
        assert FileFilter.should_skip(path) is True

    def test_case_insensitive_minified_suffix(self) -> None:
        assert FileFilter.should_skip("lib/jQuery.MIN.JS") is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/main.py",
            "src/utils.ts",
            "lib/helpers.js",
            "src/components/App.tsx",
            "README.md",
            "tests/test_main.py",
            "src/main.js",
            "frontend/src/App.js",
            "assets/app.20240101.js",  # date stamp, not bundler hash
            "static/data.12345678.css",  # purely numeric, not hex hash
            # These were previously skipped by hardcoded dirs — now they're fine by default
            "vendor/lodash.js",
            "node_modules/express/index.js",
            "dist/bundle.js",
            "build/output.js",
            "third_party/lib.js",
            "3rdparty/plugin.js",
            "bower_components/angular/angular.js",
        ],
    )
    def test_does_not_skip_normal_files_without_exclude_paths(self, path: str) -> None:
        assert FileFilter.should_skip(path) is False


class TestFileFilterExcludePaths:
    """Tests for user-configured exclude_paths parameter."""

    @pytest.mark.parametrize(
        "path",
        [
            "vendor/lodash.js",
            "src/vendor/chart.js",
            "node_modules/express/index.js",
            "deep/nested/node_modules/pkg/index.js",
            "dist/bundle.js",
            "build/output.js",
            "third_party/lib.js",
            "3rdparty/plugin.js",
            "bower_components/angular/angular.js",
        ],
    )
    def test_skips_directories_in_exclude_paths(self, path: str) -> None:
        exclude = (
            "vendor",
            "node_modules",
            "dist",
            "build",
            "third_party",
            "3rdparty",
            "bower_components",
        )
        assert FileFilter.should_skip(path, exclude_paths=exclude) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/main.py",
            "src/utils.ts",
            "lib/helpers.js",
            "src/vendor.py",  # "vendor" as filename, not directory
            "src/build_utils.py",  # "build" as prefix, not directory
            "dist.py",  # "dist" as filename, not directory
            "src/inxr2/adapters/external/treesitter/python_parser.py",
            "external/dep.js",
        ],
    )
    def test_does_not_skip_non_matching_paths(self, path: str) -> None:
        exclude = ("vendor", "node_modules", "dist", "build")
        assert FileFilter.should_skip(path, exclude_paths=exclude) is False

    def test_case_insensitive_exclude_paths(self) -> None:
        assert (
            FileFilter.should_skip(
                "Node_Modules/pkg/index.js", exclude_paths=("node_modules",)
            )
            is True
        )

    def test_backslash_path_separator(self) -> None:
        assert (
            FileFilter.should_skip(
                "node_modules\\express\\index.js", exclude_paths=("node_modules",)
            )
            is True
        )

    def test_empty_exclude_paths_does_not_skip_directories(self) -> None:
        # With no exclude_paths, vendor/node_modules are NOT skipped
        assert FileFilter.should_skip("vendor/lodash.js") is False
        assert FileFilter.should_skip("node_modules/express/index.js") is False

    def test_external_directory_not_skipped(self) -> None:
        # Regression test for issue #349: "external" was incorrectly in
        # the old hardcoded _SKIP_DIRECTORIES list, causing files under
        # src/.../external/ to be silently dropped during indexing.
        assert (
            FileFilter.should_skip(
                "src/inxr2/adapters/external/treesitter/python_parser.py"
            )
            is False
        )
        assert FileFilter.should_skip("external/dep.js") is False
        assert FileFilter.should_skip("lib/external/utils.py") is False
