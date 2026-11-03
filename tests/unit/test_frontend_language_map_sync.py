"""Guard: the frontend's language fallback map must match the backend (#589).

``frontend/src/lib/fileUtils.ts`` keeps its own extension/filename → language
map for Browse syntax highlighting when the API returns ``language: null``. It
previously drifted from :class:`LanguageDetector` (``.h`` → c instead of cpp,
missing ``.cjs``/``.cxx``/``.rake`` ...). For every language the backend can
actually parse, both maps must agree on every extension and special filename.

The frontend may map *extra* extensions (or map non-parsed languages
differently, e.g. ``.zsh`` → bash for Prism highlighting); only parser-backed
languages are pinned.

How it works: the TypeScript map is read as plain text and parsed with a
regex (one ``'key': 'value',`` entry per line), then compared against the real
backend tables imported from Python. Only languages in
``TreeSitterService.SUPPORTED_LANGUAGES`` (the ones that produce symbols) are
checked.

Trade-off (accepted for now): this is a backend test that reads a frontend
source file, so it couples the two halves of the repo. It is deterministic
(repo code only, no external data), but reformatting the TS map, e.g. several
entries on one line or double quotes, can break the regex without any real
drift. If that happens, or the coupling becomes a nuisance, it is safe to
delete this file. ``frontend/src/lib/fileUtils.test.ts`` keeps a hard-coded
table of the same cases, but that table cannot catch future drift on its own.
"""

import re
from pathlib import Path

from inxr2.adapters.external.treesitter.service import TreeSitterService
from inxr2.domain.services.language_detector import LanguageDetector

FILE_UTILS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "fileUtils.ts"
)

_ENTRY_RE = re.compile(r"^\s*'?([^'\s:]+)'?\s*:\s*'([^']+)',?\s*$")


def _parse_ts_map(source: str, name: str) -> dict[str, str]:
    """Extract a ``const NAME: Record<string, string> = { ... }`` literal."""
    match = re.search(
        rf"const {name}: Record<string, string> = \{{(.*?)\n\}}", source, re.S
    )
    assert match, f"{name} not found in {FILE_UTILS}"
    entries: dict[str, str] = {}
    for line in match.group(1).splitlines():
        entry = _ENTRY_RE.match(line)
        if entry:
            entries[entry.group(1)] = entry.group(2)
    assert entries, f"{name} parsed as empty"
    return entries


def _parsed_languages() -> set[str]:
    return set(TreeSitterService.SUPPORTED_LANGUAGES)


def test_parser_extensions_match_backend() -> None:
    frontend = _parse_ts_map(FILE_UTILS.read_text(), "EXTENSION_LANGUAGE_MAP")
    expected = {
        ext: lang
        for ext, lang in LanguageDetector.EXTENSION_MAP.items()
        if lang in _parsed_languages()
    }
    mismatches = {
        ext: (lang, frontend.get(ext))
        for ext, lang in expected.items()
        if frontend.get(ext) != lang
    }
    assert mismatches == {}, "ext: (backend, frontend)"


def test_parser_special_filenames_match_backend() -> None:
    frontend = _parse_ts_map(FILE_UTILS.read_text(), "FILENAME_LANGUAGE_MAP")
    expected = {
        name: lang
        for name, lang in LanguageDetector.FILENAME_MAP.items()
        if lang in _parsed_languages()
    }
    mismatches = {
        name: (lang, frontend.get(name))
        for name, lang in expected.items()
        if frontend.get(name) != lang
    }
    assert mismatches == {}, "filename: (backend, frontend)"


def test_supported_language_extensions_are_detected() -> None:
    """Every parser extension is also known to LanguageDetector (same truth)."""
    for lang, exts in TreeSitterService.SUPPORTED_LANGUAGES.items():
        for ext in exts:
            assert LanguageDetector.EXTENSION_MAP.get(ext) == lang, ext
