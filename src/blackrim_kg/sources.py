"""Corpus discovery: walk a project root and classify its source files.

The walker is the only part of the engine that touches the filesystem broadly.
It is deliberately conservative about what it descends into (skipping VCS,
dependency, build, and virtual-env directories) so a build never wanders into
``node_modules`` or ``.git``. Language classification is extension-based and
intentionally small — it mirrors the languages ast-lens parses, plus a few
documentation extensions the (future) docs source will consume.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass

# Extension -> language label. Kept aligned with ast-lens's supported set so the
# walker and the outline adapter agree on what counts as code.
CODE_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
}

DOC_EXT: dict[str, str] = {
    ".md": "markdown",
    ".rst": "rst",
    ".txt": "text",
}

# Directory names never descended into.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git", ".hg", ".svn",
        "node_modules", ".venv", "venv", "__pycache__",
        "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "kg-out", "graphify-out", ".gc", ".beads",
    }
)


@dataclass(frozen=True)
class DiscoveredFile:
    """A file found by the walker, with its repo-relative path and language."""

    abs_path: str
    rel_path: str
    lang: str
    category: str  # "code" | "doc"


class FilesystemWalker:
    """Walk ``root`` and yield code (and, optionally, documentation) files."""

    def __init__(
        self,
        root: str,
        *,
        include_docs: bool = False,
        skip_dirs: frozenset[str] = SKIP_DIRS,
    ) -> None:
        self.root = os.path.abspath(root)
        self.include_docs = include_docs
        self.skip_dirs = skip_dirs

    def __iter__(self) -> Iterator[DiscoveredFile]:
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Prune skipped and hidden directories in place.
            dirnames[:] = sorted(
                d for d in dirnames if d not in self.skip_dirs and not d.startswith(".")
            )
            for name in sorted(filenames):
                ext = os.path.splitext(name)[1].lower()
                lang = CODE_EXT.get(ext)
                category = "code"
                if lang is None and self.include_docs:
                    lang = DOC_EXT.get(ext)
                    category = "doc"
                if lang is None:
                    continue
                abs_path = os.path.join(dirpath, name)
                rel_path = os.path.relpath(abs_path, self.root).replace(os.sep, "/")
                yield DiscoveredFile(abs_path, rel_path, lang, category)

    def code_files(self) -> list[DiscoveredFile]:
        return [f for f in self if f.category == "code"]
