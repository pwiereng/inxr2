"""Language detection service."""

from pathlib import Path


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
        ".sh": "shell",
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
