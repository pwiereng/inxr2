"""Dependency manifest/lock file parsers.

Each parser handles one language ecosystem's manifest and lock files,
returning lists of dependency dicts that map to Dependency entities.
"""

from .csharp_deps import CSharpDependencyParser
from .java_deps import JavaDependencyParser
from .javascript_deps import JavaScriptDependencyParser
from .python_deps import PythonDependencyParser
from .service import DependencyParserService

__all__ = [
    "CSharpDependencyParser",
    "DependencyParserService",
    "JavaDependencyParser",
    "JavaScriptDependencyParser",
    "PythonDependencyParser",
]
