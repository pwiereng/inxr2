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

    def test_detect_sh_extension_is_bash(self) -> None:
        """Test that .sh and .bash files are detected as bash."""
        assert LanguageDetector.detect("script.sh") == "bash"
        assert LanguageDetector.detect("deploy.bash") == "bash"

    def test_detect_case_insensitive(self) -> None:
        """Test detection is case-insensitive for extensions."""
        assert LanguageDetector.detect("Script.PY") == "python"
        assert LanguageDetector.detect("FILE.RS") == "rust"


class TestDetectFromShebang:
    """Tests for shebang-based language detection."""

    def test_bin_bash(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/bin/bash") == "bash"

    def test_usr_bin_bash(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/bash") == "bash"

    def test_usr_bin_env_bash(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env bash") == "bash"

    def test_bin_sh(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/bin/sh") == "bash"

    def test_usr_bin_env_sh(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env sh") == "bash"

    def test_usr_local_bin_bash(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/usr/local/bin/bash") == "bash"

    def test_unknown_interpreter(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/python3") is None

    def test_empty_string(self) -> None:
        assert LanguageDetector.detect_from_shebang("") is None

    def test_non_shebang_line(self) -> None:
        assert LanguageDetector.detect_from_shebang("echo hello") is None

    def test_shebang_with_trailing_content(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/bin/bash -e") == "bash"

    def test_env_with_s_flag(self) -> None:
        assert (
            LanguageDetector.detect_from_shebang("#!/usr/bin/env -S bash -e") == "bash"
        )

    def test_bin_env_bash(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/bin/env bash") == "bash"

    def test_bin_env_s_flag(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/bin/env -S bash") == "bash"

    def test_case_insensitive_shebang(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env BASH") == "bash"

    def test_env_with_path_token(self) -> None:
        assert (
            LanguageDetector.detect_from_shebang("#!/usr/bin/env /bin/bash") == "bash"
        )

    def test_usr_local_bin_env(self) -> None:
        assert (
            LanguageDetector.detect_from_shebang("#!/usr/local/bin/env bash") == "bash"
        )

    def test_crlf_shebang(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/bin/bash\r") == "bash"

    def test_crlf_env_shebang(self) -> None:
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env bash\r") == "bash"


class TestShebangAndTextFileBranches:
    """Branch coverage for shebang env-skipping and is_text_file edges."""

    def test_shebang_env_with_only_flags(self) -> None:
        # All tokens are flags → loop exhausts → returns None.
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env -S") is None

    def test_shebang_env_token_is_env(self) -> None:
        # A literal "env" token is skipped; nothing else → None.
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env env") is None

    def test_shebang_env_flag_then_interpreter(self) -> None:
        # Flag skipped, then real interpreter resolves.
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env -S bash") == "bash"

    def test_shebang_direct_env_returns_none(self) -> None:
        # Direct /bin/env path (no args) → interpreter "env" → None.
        assert LanguageDetector.detect_from_shebang("#!/usr/bin/env") is None

    def test_is_text_file_no_extension(self) -> None:
        assert LanguageDetector.is_text_file("Makefile") is True

    def test_is_text_file_known_config_extension(self) -> None:
        assert LanguageDetector.is_text_file("poetry.lock") is True

    def test_is_text_file_unknown_extension(self) -> None:
        assert LanguageDetector.is_text_file("mystery.xyz") is False
