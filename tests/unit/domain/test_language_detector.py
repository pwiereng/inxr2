"""Tests for language detection service."""

from pathlib import Path

from inxr2.domain.services.language_detector import LanguageDetector


class TestLanguageDetector:
    """Tests for LanguageDetector service."""

    def test_detect_python(self) -> None:
        """Test detecting Python files."""
        language = LanguageDetector.detect("test.py")
        assert language == "python"

    def test_detect_typescript(self) -> None:
        """Test detecting TypeScript files."""
        language = LanguageDetector.detect("component.tsx")
        assert language == "typescript"

    def test_detect_javascript(self) -> None:
        """Test detecting JavaScript files."""
        language = LanguageDetector.detect("script.js")
        assert language == "javascript"

    def test_detect_markdown(self) -> None:
        """Test detecting Markdown files."""
        language = LanguageDetector.detect("README.md")
        assert language == "markdown"

    def test_detect_with_path_object(self) -> None:
        """Test detection with Path object."""
        language = LanguageDetector.detect(Path("src/main.rs"))
        assert language == "rust"

    def test_detect_dockerfile(self) -> None:
        """Test detecting Dockerfile by filename."""
        language = LanguageDetector.detect("Dockerfile")
        assert language == "dockerfile"

    def test_detect_makefile(self) -> None:
        """Test detecting Makefile by filename."""
        language = LanguageDetector.detect("Makefile")
        assert language == "makefile"

    def test_detect_unknown_extension(self) -> None:
        """Test unknown file extension returns None."""
        language = LanguageDetector.detect("file.xyz123")
        assert language is None

    def test_detect_no_extension(self) -> None:
        """Test file with no extension returns None."""
        language = LanguageDetector.detect("randomfile")
        assert language is None

    def test_detect_svg(self) -> None:
        """Test detecting SVG files as text (XML-based)."""
        assert LanguageDetector.detect("icon.svg") == "svg"

    def test_is_text_file_svg(self) -> None:
        """Test that SVG files are identified as text (XML-based, not binary)."""
        assert LanguageDetector.is_text_file("icon.svg") is True

    def test_is_text_file_image_files(self) -> None:
        """Test text file detection for image files."""
        assert LanguageDetector.is_text_file("image.png") is False
        assert LanguageDetector.is_text_file("photo.jpg") is False

    def test_is_text_file_compiled_files(self) -> None:
        """Test text file detection for compiled files."""
        assert LanguageDetector.is_text_file("program.exe") is False
        assert LanguageDetector.is_text_file("library.so") is False
        assert LanguageDetector.is_text_file("app.pyc") is False

    def test_is_text_file_archive_files(self) -> None:
        """Test text file detection for archive files."""
        assert LanguageDetector.is_text_file("archive.zip") is False
        assert LanguageDetector.is_text_file("backup.tar.gz") is False

    def test_is_text_file_text_files(self) -> None:
        """Test that text files are correctly identified."""
        assert LanguageDetector.is_text_file("script.py") is True
        assert LanguageDetector.is_text_file("README.md") is True
        assert LanguageDetector.is_text_file("config.json") is True

    def test_detect_rakefile(self) -> None:
        """Test detecting Rakefile as Ruby by filename."""
        assert LanguageDetector.detect("Rakefile") == "ruby"

    def test_detect_gemfile(self) -> None:
        """Test detecting Gemfile as Ruby by filename."""
        assert LanguageDetector.detect("Gemfile") == "ruby"

    def test_detect_ruby_extensions(self) -> None:
        """Test detecting Ruby files by extension."""
        assert LanguageDetector.detect("app.rb") == "ruby"
        assert LanguageDetector.detect("tasks.rake") == "ruby"

    def test_detect_case_insensitive(self) -> None:
        """Test detection is case-insensitive for extensions."""
        assert LanguageDetector.detect("Script.PY") == "python"
        assert LanguageDetector.detect("FILE.RS") == "rust"
