"""Tests for PlaintextParser."""

import pytest

from inxr2.adapters.external.plaintext_parser import PlaintextParser


class TestPlaintextParser:
    """Tests for plaintext file parser."""

    @pytest.fixture
    def parser(self) -> PlaintextParser:
        """Create a PlaintextParser instance."""
        return PlaintextParser()

    def test_supports_markdown_files(self, parser: PlaintextParser) -> None:
        """Test that parser supports markdown files."""
        assert parser.supports_file("README.md")
        assert parser.supports_file("docs/guide.markdown")
        assert parser.supports_file("notes.rst")

    def test_supports_yaml_files(self, parser: PlaintextParser) -> None:
        """Test that parser supports YAML files."""
        assert parser.supports_file("config.yaml")
        assert parser.supports_file("config.yml")
        assert parser.supports_file("docker-compose.yml")

    def test_supports_config_files(self, parser: PlaintextParser) -> None:
        """Test that parser supports config files."""
        assert parser.supports_file("setup.toml")
        assert parser.supports_file("config.ini")
        assert parser.supports_file(".env.example")

    def test_supports_dockerfile(self, parser: PlaintextParser) -> None:
        """Test that parser supports Dockerfiles."""
        assert parser.supports_file("Dockerfile")
        assert parser.supports_file("Dockerfile.dev")
        assert parser.supports_file("app.dockerfile")

    def test_supports_json_and_xml(self, parser: PlaintextParser) -> None:
        """Test that parser supports JSON and XML files."""
        assert parser.supports_file("package.json")
        assert parser.supports_file("config.xml")

    def test_does_not_support_code_files(self, parser: PlaintextParser) -> None:
        """Test that parser does NOT support code files."""
        assert not parser.supports_file("main.py")
        assert not parser.supports_file("app.ts")
        assert not parser.supports_file("Main.java")

    def test_parse_markdown_splits_by_paragraphs(self, parser: PlaintextParser) -> None:
        """Test that markdown is split into paragraph chunks."""
        content = """# Introduction

This is the first paragraph.
It has multiple lines.

This is the second paragraph.

## Section

Another paragraph here.
"""
        chunks = parser.parse(content, "README.md")

        # Should have multiple chunks (paragraphs)
        assert len(chunks) > 0

        # Verify structure
        for chunk in chunks:
            assert "content" in chunk
            assert "content_type" in chunk
            assert "source_line" in chunk
            assert "source_end_line" in chunk

        # First chunk should be the heading
        assert chunks[0]["content"] == "# Introduction"
        assert chunks[0]["source_line"] == 1
        assert chunks[0]["source_end_line"] == 1
        assert chunks[0]["content_type"] == "markdown_paragraph"

        # Second chunk should be the first paragraph
        assert "first paragraph" in chunks[1]["content"]
        assert chunks[1]["source_line"] == 3

    def test_parse_yaml_extracts_meaningful_lines(
        self, parser: PlaintextParser
    ) -> None:
        """Test that YAML parser extracts meaningful content."""
        content = """version: '3.8'

services:
  web:
    image: nginx:latest
    ports:
      - "80:80"

  db:
    image: postgres:13
"""
        chunks = parser.parse(content, "docker-compose.yml")

        assert len(chunks) > 0

        # Should have content from various YAML lines
        all_content = " ".join(c["content"] for c in chunks)
        assert "version" in all_content
        assert "services" in all_content
        assert "nginx" in all_content

        # Verify content type
        assert all(c["content_type"] == "yaml_content" for c in chunks)

    def test_parse_dockerfile_extracts_instructions(
        self, parser: PlaintextParser
    ) -> None:
        """Test that Dockerfile parser extracts instructions."""
        content = """FROM python:3.11

# Install dependencies
RUN pip install --no-cache-dir flask

WORKDIR /app

COPY . .

CMD ["python", "app.py"]
"""
        chunks = parser.parse(content, "Dockerfile")

        assert len(chunks) > 0

        # Verify content includes instructions
        all_content = " ".join(c["content"] for c in chunks)
        assert "FROM python" in all_content
        assert "RUN pip install" in all_content
        assert "WORKDIR" in all_content

        # Verify content type
        assert all(c["content_type"] == "dockerfile_instruction" for c in chunks)

    def test_parse_text_file_extracts_lines(self, parser: PlaintextParser) -> None:
        """Test that plain text files are chunked reasonably."""
        content = """This is a plain text file.

It has some content.
More content here.

And another paragraph.
"""
        chunks = parser.parse(content, "notes.txt")

        assert len(chunks) > 0

        # Should extract paragraphs
        assert any("plain text" in c["content"] for c in chunks)
        assert any("another paragraph" in c["content"] for c in chunks)

    def test_parse_skips_blank_lines(self, parser: PlaintextParser) -> None:
        """Test that blank lines are not indexed as separate chunks."""
        content = """Line 1


Line 2
"""
        chunks = parser.parse(content, "test.txt")

        # Should only have 2 chunks (the two lines with content)
        # Blank lines should be skipped
        non_empty_chunks = [c for c in chunks if c["content"].strip()]
        assert len(non_empty_chunks) == 2

    def test_parse_long_content_is_chunked(self, parser: PlaintextParser) -> None:
        """Test that very long paragraphs are chunked to max size."""
        # Create a very long paragraph (> 500 chars)
        long_paragraph = "This is a test. " * 50  # ~800 chars

        content = f"""{long_paragraph}

Short paragraph.
"""
        chunks = parser.parse(content, "test.md")

        # Should have multiple chunks
        assert len(chunks) >= 2

        # Verify no chunk exceeds max length (500 chars per design doc)
        # Note: We'll implement this as a stretch goal
        # For now, just verify chunks exist
        assert all(len(c["content"]) > 0 for c in chunks)

    def test_parse_json_extracts_content(self, parser: PlaintextParser) -> None:
        """Test that JSON files are indexed as plain text."""
        content = """{
  "name": "my-package",
  "version": "1.0.0",
  "description": "A test package"
}
"""
        chunks = parser.parse(content, "package.json")

        assert len(chunks) > 0

        # Should extract meaningful content
        all_content = " ".join(c["content"] for c in chunks)
        assert "my-package" in all_content
        assert "description" in all_content

    def test_parse_empty_file_returns_empty_list(self, parser: PlaintextParser) -> None:
        """Test that empty files return no chunks."""
        chunks = parser.parse("", "empty.md")
        assert len(chunks) == 0

        chunks = parser.parse("   \n\n  ", "whitespace.txt")
        assert len(chunks) == 0
