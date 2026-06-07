"""The graph model: an original node/edge taxonomy for a code-first knowledge graph.

Two ideas drive this model and distinguish it from a heuristic, single-tier
graph:

1. **A precise spine, separable enrichment.** Every node and edge records how it
   was derived (:class:`Provenance`) and how much to trust it (:class:`Confidence`).
   The structural spine — files, symbols, containment, imports drawn from
   ``ast-lens`` — is ``Provenance.AST`` / ``Confidence.EXACT``. Inferred or
   resolved relationships carry weaker provenance/confidence. A consumer can
   always filter the graph down to "only what is exactly true" without losing
   the richer, fuzzier layers.

2. **Stable, human-readable IDs.** Node IDs are derived from durable facts
   (repo-relative path, declaration kind, name) rather than positional offsets,
   so a graph diff across edits stays small. Line spans are carried as
   attributes and used only as a last-resort disambiguator, never as the
   primary key.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from enum import StrEnum


class NodeKind(StrEnum):
    """The category of a graph node."""

    MODULE = "module"      # a package / directory / logical module boundary
    FILE = "file"          # a single source or artifact file
    SYMBOL = "symbol"      # a declaration; the specific kind is in attrs["symbol_kind"]
    IMPORT = "import"      # an imported module reference
    DOC = "doc"            # a documentation file or section
    CONCEPT = "concept"    # a semantic/domain concept (enrichment only)


class SymbolKind(StrEnum):
    """The declaration kind carried on a :data:`NodeKind.SYMBOL` node."""

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    TYPE = "type"
    INTERFACE = "interface"
    ENUM = "enum"
    CONSTANT = "constant"
    VARIABLE = "variable"
    OTHER = "other"


class EdgeKind(StrEnum):
    """The relationship a directed edge expresses (always ``src`` -> ``dst``)."""

    CONTAINS = "contains"        # file/module/class contains a child declaration
    IMPORTS = "imports"          # a file/module imports another module
    CALLS = "calls"              # a symbol calls another symbol
    REFERENCES = "references"    # a symbol references another symbol (type use, etc.)
    INHERITS = "inherits"        # a type inherits from another type
    IMPLEMENTS = "implements"    # a type implements an interface
    DOCUMENTS = "documents"      # a doc node documents a symbol/file
    MENTIONS = "mentions"        # a doc/concept mentions a symbol/concept
    RELATES_TO = "relates_to"    # an inferred semantic relationship


class Provenance(StrEnum):
    """How a node or edge entered the graph."""

    AST = "ast"            # exact structure from ast-lens / a tree-sitter pass
    FS = "fs"              # filesystem structure (a file exists, a dir contains it)
    DOC = "doc"            # parsed from documentation
    INFERRED = "inferred"  # heuristic or model-derived enrichment


class Confidence(StrEnum):
    """How much to trust an edge (and, transitively, the graph slice it is in)."""

    EXACT = "exact"        # literally present in the parsed source / filesystem
    RESOLVED = "resolved"  # produced by deterministic cross-file resolution
    INFERRED = "inferred"  # heuristic or probabilistic


@dataclass(frozen=True)
class Span:
    """A 1-based, inclusive line range within a file."""

    start_line: int
    end_line: int

    def to_dict(self) -> dict:
        return {"start_line": self.start_line, "end_line": self.end_line}

    @classmethod
    def from_dict(cls, d: dict | None) -> Span | None:
        if not d:
            return None
        return cls(int(d["start_line"]), int(d["end_line"]))


@dataclass
class Node:
    """A vertex in the knowledge graph.

    ``id`` is the stable primary key; ``attrs`` carries kind-specific extras
    (for a symbol: ``symbol_kind``, ``signature``, ``private``; for a file:
    ``loc``; and so on) so the core schema stays small while remaining
    extensible.
    """

    id: str
    kind: NodeKind
    label: str
    path: str | None = None
    lang: str | None = None
    span: Span | None = None
    provenance: Provenance = Provenance.AST
    attrs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "provenance": self.provenance.value,
        }
        if self.path is not None:
            d["path"] = self.path
        if self.lang is not None:
            d["lang"] = self.lang
        if self.span is not None:
            d["span"] = self.span.to_dict()
        if self.attrs:
            d["attrs"] = dict(self.attrs)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Node:
        return cls(
            id=d["id"],
            kind=NodeKind(d["kind"]),
            label=d["label"],
            path=d.get("path"),
            lang=d.get("lang"),
            span=Span.from_dict(d.get("span")),
            provenance=Provenance(d.get("provenance", Provenance.AST.value)),
            attrs=dict(d.get("attrs", {})),
        )


@dataclass
class Edge:
    """A directed, typed relationship between two nodes (``src`` -> ``dst``)."""

    src: str
    dst: str
    kind: EdgeKind
    provenance: Provenance = Provenance.AST
    confidence: Confidence = Confidence.EXACT
    weight: float = 1.0
    attrs: dict = field(default_factory=dict)

    def key(self) -> tuple[str, str, str, str]:
        """The identity tuple used to dedup edges: (src, dst, kind, provenance)."""
        return (self.src, self.dst, self.kind.value, self.provenance.value)

    def to_dict(self) -> dict:
        d: dict = {
            "src": self.src,
            "dst": self.dst,
            "kind": self.kind.value,
            "provenance": self.provenance.value,
            "confidence": self.confidence.value,
            "weight": self.weight,
        }
        if self.attrs:
            d["attrs"] = dict(self.attrs)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Edge:
        return cls(
            src=d["src"],
            dst=d["dst"],
            kind=EdgeKind(d["kind"]),
            provenance=Provenance(d.get("provenance", Provenance.AST.value)),
            confidence=Confidence(d.get("confidence", Confidence.EXACT.value)),
            weight=float(d.get("weight", 1.0)),
            attrs=dict(d.get("attrs", {})),
        )


# --- stable ID helpers ------------------------------------------------------
#
# IDs use a short ``scheme:body`` form. The body is built from durable facts so
# IDs survive edits that move code around within a file. Use forward slashes
# everywhere so a graph built on one OS is portable to another.


def normalize_path(rel_path: str) -> str:
    """Normalize a repo-relative path to a portable, forward-slash form."""
    return posixpath.normpath(rel_path.replace("\\", "/")).lstrip("./")


def module_id(dotted_or_path: str) -> str:
    body = dotted_or_path.replace("\\", "/").strip("/")
    return f"mod:{body}"


def file_id(rel_path: str) -> str:
    return f"file:{normalize_path(rel_path)}"


def symbol_id(rel_path: str, symbol_kind: SymbolKind | str, name: str) -> str:
    kind = symbol_kind.value if isinstance(symbol_kind, SymbolKind) else str(symbol_kind)
    return f"sym:{normalize_path(rel_path)}#{kind}:{name}"


def import_id(rel_path: str, module: str) -> str:
    return f"imp:{normalize_path(rel_path)}->{module}"


def doc_id(rel_path: str, anchor: str | None = None) -> str:
    base = f"doc:{normalize_path(rel_path)}"
    return f"{base}#{anchor}" if anchor else base


def disambiguate(base_id: str, span: Span | None) -> str:
    """Append a line-span suffix to break an ID collision (last resort only)."""
    if span is None:
        return base_id
    return f"{base_id}@{span.start_line}-{span.end_line}"
