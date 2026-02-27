"""Tree-sitter parsing module.

Provides language-agnostic code parsing and symbol extraction
using tree-sitter grammars with language-specific parsers.

To add a new language:
1. Create a new parser class extending BaseLanguageParser
2. Register it in TreeSitterService._ensure_initialized()
3. Add the language to SUPPORTED_LANGUAGES
"""

from .base import BaseLanguageParser
from .c_parser import CParser
from .cpp_parser import CppParser
from .csharp_parser import CSharpParser
from .go_parser import GoParser
from .java_parser import JavaParser
from .python_parser import PythonParser
from .service import TreeSitterService
from .typescript_parser import TypeScriptParser

__all__ = [
    "TreeSitterService",
    "BaseLanguageParser",
    "CParser",
    "CppParser",
    "CSharpParser",
    "GoParser",
    "JavaParser",
    "PythonParser",
    "TypeScriptParser",
]
