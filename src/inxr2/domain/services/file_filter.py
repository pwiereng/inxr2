"""File filter service for skipping minified/bundled files during indexing."""

import re

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
    def should_skip(file_path: str, exclude_paths: tuple[str, ...] = ()) -> bool:
        """Return True if the file should be skipped.

        Skips minified/bundled files unconditionally. Skips files whose path
        contains a directory segment matching any entry in ``exclude_paths``.

        Args:
            file_path: Repository-relative file path (e.g., "src/main.py").
            exclude_paths: Directory names to exclude (e.g., ("vendor", "dist")).
                           Matched case-insensitively against each path segment.
        """
        lower = file_path.lower()

        # Check minified suffixes
        if lower.endswith(_MINIFIED_SUFFIXES):
            return True

        # Check bundler hash pattern (e.g., app.a1b2c3d4.js)
        if _BUNDLE_HASH_RE.search(lower):
            return True

        # Check user-configured excluded directory names
        if exclude_paths:
            excluded = {p.lower() for p in exclude_paths}
            parts = lower.replace("\\", "/").split("/")
            for part in parts:
                if part in excluded:
                    return True

        return False
