"""Language detection service."""

import re
from pathlib import Path

# Matches two shebang forms:
#   1. Direct path: #!/bin/bash, #!/usr/bin/bash, #!/usr/local/bin/bash
#   2. env-based:   #!/usr/bin/env bash, #!/bin/env -S bash -e
# For env shebangs, flags (words starting with -) are skipped to find
# the interpreter name.
_SHEBANG_DIRECT_RE = re.compile(r"^#!\s*/(?:usr/)?(?:local/)?bin/(\S+)")
_SHEBANG_ENV_RE = re.compile(r"^#!\s*/(?:usr/)?(?:local/)?bin/env\s+(.*)")

_SHEBANG_LANGUAGE_MAP: dict[str, str] = {
    "bash": "bash",
    "sh": "bash",
}


class LanguageDetector:
    """
    Detect programming language from file extension.

    This is a simple extension-based detector for the initial vertical slice.
    Future: Could use tree-sitter or other sophisticated detection.
    """

    EXTENSION_MAP = {
        # Python
        ".py": "python",
        ".pyi": "python",
        ".pyx": "python",
        # JavaScript/TypeScript
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mts": "typescript",
        ".cts": "typescript",
        # Web
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "scss",
        ".sass": "sass",
        ".less": "less",
        # Java/JVM
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".scala": "scala",
        ".groovy": "groovy",
        # C/C++
        ".c": "c",
        ".h": "cpp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c++": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
        ".h++": "cpp",
        # C#
        ".cs": "csharp",
        # Go
        ".go": "go",
        # Rust
        ".rs": "rust",
        # Ruby
        ".rb": "ruby",
        ".rake": "ruby",
        # PHP
        ".php": "php",
        # Swift
        ".swift": "swift",
        # Objective-C
        ".m": "objective-c",
        ".mm": "objective-cpp",
        # Shell
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".fish": "fish",
        # Configuration
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".xml": "xml",
        # Markdown/Docs
        ".md": "markdown",
        ".rst": "restructuredtext",
        ".txt": "text",
        # SVG (XML-based text format)
        ".svg": "svg",
        # SQL
        ".sql": "sql",
        # Docker
        ".dockerfile": "dockerfile",
        # Makefile
        ".mk": "makefile",
    }

    FILENAME_MAP = {
        "Dockerfile": "dockerfile",
        "Makefile": "makefile",
        "CMakeLists.txt": "cmake",
        "Rakefile": "ruby",
        "Gemfile": "ruby",
        ".gitignore": "gitignore",
        ".dockerignore": "dockerignore",
    }

    @classmethod
    def detect(cls, file_path: str | Path) -> str | None:
        """
        Detect language from file path.

        Args:
            file_path: Path to the file

        Returns:
            Language name (lowercase) or None if unknown
        """
        path = Path(file_path)

        # Check filename first (e.g., "Dockerfile")
        if path.name in cls.FILENAME_MAP:
            return cls.FILENAME_MAP[path.name]

        # Check extension
        extension = path.suffix.lower()
        if extension in cls.EXTENSION_MAP:
            return cls.EXTENSION_MAP[extension]

        return None

    @classmethod
    def detect_from_shebang(cls, first_line: str) -> str | None:
        """Detect language from a shebang line (e.g. ``#!/bin/bash``).

        Handles direct paths (``#!/bin/bash``) and env-based shebangs
        including ``env -S`` flags (``#!/usr/bin/env -S bash -e``).

        Args:
            first_line: The first line of the file content.

        Returns:
            Language name (lowercase) or None if unrecognised.
        """
        # Strip trailing \r for CRLF line endings
        first_line = first_line.rstrip("\r")

        # Try env-based shebang first (more specific match)
        env_match = _SHEBANG_ENV_RE.match(first_line)
        if env_match:
            # Skip flags (words starting with -) to find the interpreter
            for token in env_match.group(1).split():
                if token.startswith("-"):
                    continue
                # Normalize: handle paths (/bin/bash) and casing (BASH)
                interpreter = Path(token).name.lower()
                if interpreter == "env":
                    continue
                return _SHEBANG_LANGUAGE_MAP.get(interpreter)
            return None

        # Try direct path shebang
        direct_match = _SHEBANG_DIRECT_RE.match(first_line)
        if direct_match:
            interpreter = Path(direct_match.group(1)).name.lower()
            # The regex may capture "env" for /bin/env — skip it
            if interpreter == "env":
                return None
            return _SHEBANG_LANGUAGE_MAP.get(interpreter)

        return None

    @classmethod
    def is_text_file(cls, file_path: str | Path) -> bool:
        """
        Check if file is likely a text file (not binary).

        Args:
            file_path: Path to the file

        Returns:
            True if file is likely text, False otherwise
        """
        path = Path(file_path)

        # Binary extensions to skip
        binary_extensions = {
            ".pyc",
            ".pyo",
            ".pyd",
            ".so",
            ".dylib",
            ".dll",
            ".exe",
            ".bin",
            ".dat",
            ".db",
            ".sqlite",
            ".sqlite3",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".ico",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
            ".bz2",
            ".xz",
            ".7z",
            ".rar",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".otf",
        }

        extension = path.suffix.lower()
        if extension in binary_extensions:
            return False

        # If we detected a language, it's probably text
        if cls.detect(file_path):
            return True

        # Common text files without extensions or unknown extensions
        # Be inclusive - include files without extensions or unknown extensions
        # as they are often config files, READMEs, etc.
        if not extension or extension in {
            ".lock",
            ".env",
            ".cfg",
            ".conf",
            ".properties",
            ".editorconfig",
            ".prettierrc",
            ".eslintrc",
        }:
            return True

        return False
