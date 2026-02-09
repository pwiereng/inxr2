"""
Plaintext parser for non-code files.

Handles markdown, YAML, config files, Dockerfiles, and other text-based formats.
"""

from pathlib import Path

from inxr2.application.ports.services import PlaintextParserPort


class PlaintextParser(PlaintextParserPort):
    """
    Parser for non-code text files.

    Extracts searchable content from markdown, YAML, config files, etc.
    and chunks them appropriately for text search indexing.
    """

    # File extensions that this parser supports
    SUPPORTED_EXTENSIONS = {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".json",
        ".xml",
        ".env.example",
        ".gitignore",
        ".dockerignore",
    }

    # Special filenames without extensions
    SUPPORTED_FILENAMES = {
        "Dockerfile",
        "README",
        "LICENSE",
        "CHANGELOG",
        "CONTRIBUTING",
    }

    def supports_file(self, file_path: str) -> bool:
        """
        Check if this parser supports the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if file is supported, False otherwise
        """
        path = Path(file_path)
        name = path.name

        # Check for special filenames first (e.g., .env.example, .gitignore)
        if name in self.SUPPORTED_EXTENSIONS:
            return True

        # Check extension
        if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
            return True

        # Check filename (case-insensitive)
        if name in self.SUPPORTED_FILENAMES:
            return True

        # Check for Dockerfile variants (Dockerfile.dev, app.dockerfile, etc.)
        if "dockerfile" in name.lower():
            return True

        return False

    def parse(self, content: str, file_path: str) -> list[dict]:
        """
        Parse file into searchable chunks.

        Args:
            content: File content as string
            file_path: Path to the file (for type detection)

        Returns:
            List of dicts with keys:
            - content: The chunk text
            - content_type: Type of content (markdown_paragraph, yaml_content, etc.)
            - source_line: Starting line number (1-indexed)
            - source_end_line: Ending line number (1-indexed)
        """
        if not content or not content.strip():
            return []

        path = Path(file_path)

        # Detect file type and use appropriate parsing strategy
        if path.suffix.lower() in {".md", ".markdown", ".rst"}:
            return self._parse_markdown(content)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            return self._parse_yaml(content)
        elif "dockerfile" in path.name.lower():
            return self._parse_dockerfile(content)
        elif path.suffix.lower() in {".json", ".xml"}:
            return self._parse_structured_text(content, "json_content")
        else:
            # Default: treat as plain text
            return self._parse_plain_text(content)

    def _parse_markdown(self, content: str) -> list[dict]:
        """
        Parse markdown content into paragraph chunks.

        Splits by blank lines to create logical paragraphs.
        """
        chunks: list[dict] = []
        lines = content.split("\n")
        current_paragraph: list[str] = []
        current_start_line = 1

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()

            if not stripped:
                # Blank line - end current paragraph
                if current_paragraph:
                    chunks.append(
                        {
                            "content": "\n".join(current_paragraph),
                            "content_type": "markdown_paragraph",
                            "source_line": current_start_line,
                            "source_end_line": i - 1,
                        }
                    )
                    current_paragraph = []
            else:
                # Non-blank line - add to current paragraph
                if not current_paragraph:
                    current_start_line = i
                current_paragraph.append(line)

        # Don't forget the last paragraph
        if current_paragraph:
            chunks.append(
                {
                    "content": "\n".join(current_paragraph),
                    "content_type": "markdown_paragraph",
                    "source_line": current_start_line,
                    "source_end_line": len(lines),
                }
            )

        return chunks

    def _parse_yaml(self, content: str) -> list[dict]:
        """
        Parse YAML content into meaningful chunks.

        Groups related lines together (e.g., key-value pairs).
        """
        chunks: list[dict] = []
        lines = content.split("\n")
        current_chunk: list[str] = []
        current_start_line = 1

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                # Blank line or comment - end current chunk
                if current_chunk:
                    chunks.append(
                        {
                            "content": "\n".join(current_chunk),
                            "content_type": "yaml_content",
                            "source_line": current_start_line,
                            "source_end_line": i - 1,
                        }
                    )
                    current_chunk = []
            else:
                # Meaningful line - add to current chunk
                if not current_chunk:
                    current_start_line = i
                current_chunk.append(line)

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(
                {
                    "content": "\n".join(current_chunk),
                    "content_type": "yaml_content",
                    "source_line": current_start_line,
                    "source_end_line": len(lines),
                }
            )

        return chunks

    def _parse_dockerfile(self, content: str) -> list[dict]:
        """
        Parse Dockerfile content into instruction chunks.

        Each Dockerfile instruction (FROM, RUN, COPY, etc.) becomes a chunk.
        """
        chunks: list[dict] = []
        lines = content.split("\n")
        current_instruction: list[str] = []
        current_start_line = 1

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Skip blank lines and comments (unless part of an instruction)
            if not stripped:
                if current_instruction:
                    # Blank line ends current instruction
                    chunks.append(
                        {
                            "content": "\n".join(current_instruction),
                            "content_type": "dockerfile_instruction",
                            "source_line": current_start_line,
                            "source_end_line": i - 1,
                        }
                    )
                    current_instruction = []
                continue

            if stripped.startswith("#") and not current_instruction:
                # Standalone comment - skip
                continue

            # Check if this is a new instruction (starts with uppercase word)
            is_new_instruction = (
                stripped
                and not stripped.startswith("#")
                and stripped.split()[0].isupper()
            )

            if is_new_instruction and current_instruction:
                # Save previous instruction
                chunks.append(
                    {
                        "content": "\n".join(current_instruction),
                        "content_type": "dockerfile_instruction",
                        "source_line": current_start_line,
                        "source_end_line": i - 1,
                    }
                )
                current_instruction = []

            # Add line to current instruction
            if not current_instruction:
                current_start_line = i
            current_instruction.append(line)

        # Don't forget the last instruction
        if current_instruction:
            chunks.append(
                {
                    "content": "\n".join(current_instruction),
                    "content_type": "dockerfile_instruction",
                    "source_line": current_start_line,
                    "source_end_line": len(lines),
                }
            )

        return chunks

    def _parse_structured_text(self, content: str, content_type: str) -> list[dict]:
        """
        Parse structured text (JSON, XML) line by line.

        Skips blank lines, groups meaningful content.
        """
        chunks: list[dict] = []
        lines = content.split("\n")
        current_chunk: list[str] = []
        current_start_line = 1

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()

            if not stripped:
                # Blank line - end current chunk
                if current_chunk:
                    chunks.append(
                        {
                            "content": "\n".join(current_chunk),
                            "content_type": content_type,
                            "source_line": current_start_line,
                            "source_end_line": i - 1,
                        }
                    )
                    current_chunk = []
            else:
                # Meaningful line - add to current chunk
                if not current_chunk:
                    current_start_line = i
                current_chunk.append(line)

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(
                {
                    "content": "\n".join(current_chunk),
                    "content_type": content_type,
                    "source_line": current_start_line,
                    "source_end_line": len(lines),
                }
            )

        return chunks

    def _parse_plain_text(self, content: str) -> list[dict]:
        """
        Parse plain text into paragraph chunks.

        Similar to markdown but simpler.
        """
        # Reuse markdown parsing for plain text
        chunks = self._parse_markdown(content)

        # Change content_type to plain_text
        for chunk in chunks:
            chunk["content_type"] = "plain_text"

        return chunks
