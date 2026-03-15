"""File filter service for skipping vendor/minified files during indexing."""

import re

# Directories whose contents should be skipped entirely.
# Matched as path segments (e.g., "vendor/" anywhere in path).
_SKIP_DIRECTORIES: set[str] = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    "third_party",
    "3rdparty",
    "bower_components",
}

# Suffixes indicating minified files.
_MINIFIED_SUFFIXES: tuple[str, ...] = (
    ".min.js",
    ".min.css",
    ".min.mjs",
    ".bundle.js",
    ".bundle.css",
)

# Regex to detect common bundler output filenames with a hex hash segment
# (e.g., app.abc123ef.js). Uses a negative lookahead to exclude purely numeric
# segments like date stamps (e.g., app.20240101.js).
_BUNDLE_HASH_RE = re.compile(r"\.(?!\d{8,}\.)(?:[a-f0-9]{8,})\.(?:js|css|mjs)$")


class FileFilter:
    """Determines whether a file path should be skipped during indexing."""

    @staticmethod
    def should_skip(file_path: str) -> bool:
        """Return True if the file should be skipped (vendor/minified/bundled).

        Args:
            file_path: Repository-relative file path (e.g., "src/main.py").
        """
        lower = file_path.lower()

        # Check minified suffixes
        if lower.endswith(_MINIFIED_SUFFIXES):
            return True

        # Check if any path segment is a skip directory
        parts = lower.replace("\\", "/").split("/")
        for part in parts:
            if part in _SKIP_DIRECTORIES:
                return True

        # Check bundler hash pattern (e.g., app.a1b2c3d4.js)
        if _BUNDLE_HASH_RE.search(lower):
            return True

        return False
