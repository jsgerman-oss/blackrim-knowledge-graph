"""Adapter that turns ``ast-lens`` output into knowledge-graph nodes and edges.

``ast-lens`` is the precise structural source for the graph. It emits, per file,
a deterministic Markdown *outline* (its "App C" schema): the module doc, the
imported module names, and a bulleted list of declarations grouped under
``## Types`` / ``## Functions`` / ``## Values``, each with a visibility marker
and a ``(L<start>-<end>)`` line span.

Two facts about ast-lens shape this adapter (see ARCHITECTURE.md
§"How ast-lens feeds the graph"):

- Its ``--format json`` envelope structures only ``file`` / ``lang`` / ``loc`` /
  ``tokens_outline`` and carries the outline itself as a ``markdown`` string; the
  structured declaration objects are internal. So the **stable, version-pinned
  contract we parse is the outline Markdown schema**, not a private API.
- The outline is a *structure* emitter: it tells us which symbols exist, where,
  of what kind, and whether they are private. It does **not** emit cross-file
  references or call edges — those are a separate resolution layer. This adapter
  therefore produces only the exact spine: file nodes, symbol nodes, ``contains``
  edges, and (coarse) ``imports`` edges.

The Markdown parser below is pure and fully testable without ast-lens installed;
:func:`run_outline` is the only part that shells out, and it degrades to
``None`` (never raises) whenever ast-lens is absent or passes a file through.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

from .graph import KnowledgeGraph
from .model import (
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    Provenance,
    Span,
    SymbolKind,
    file_id,
    import_id,
    symbol_id,
)

# --- outline Markdown grammar (ast-lens "App C" schema) ---------------------
#
# Line spans render with an EN DASH (U+2013) in ast-lens; accept a plain hyphen
# too so the parser is robust to either rendering.
_DASH = "–-"
_HEADER_RE = re.compile(
    r"^#\s+(?P<file>.+?)\s+\((?P<loc>\d+)\s+LoC,\s+(?P<decls>\d+)\s+decls?\)\s*$"
)
_SECTION_RE = re.compile(r"^##\s+(?P<name>Imports|Types|Functions|Values)\s*$")
_DECL_RE = re.compile(
    r"^- `(?P<sig>.+)`(?:\s+\*\((?P<vis>private)\)\*)?\s+"
    rf"\(L(?P<l0>\d+)[{_DASH}](?P<l1>\d+)\)\s*$"
)
_VALUE_RE = re.compile(
    r"^- `(?P<name>.+)`\s+\((?P<kind>[^,]+),\s+"
    rf"L(?P<l0>\d+)[{_DASH}](?P<l1>\d+)\)\s*$"
)
_NESTED_RE = re.compile(
    rf"^\s+- (?P<label>.+?)\s+\(L(?P<l0>\d+)[{_DASH}](?P<l1>\d+)\)\s*$"
)
_PRIVATE_COUNT_RE = re.compile(r"^_\(\+(?P<n>\d+) private decls?\)_\s*$")


@dataclass
class Decl:
    """One declaration parsed from an outline section."""

    section: str          # "Types" | "Functions" | "Values"
    name: str
    sig: str
    symbol_kind: SymbolKind
    span: Span
    private: bool = False
    nested: list[tuple[str, Span]] = field(default_factory=list)


@dataclass
class ParsedOutline:
    """The structured form of one file's outline."""

    file: str | None
    loc: int | None
    decl_count: int | None
    module_doc: str | None
    imports: list[str]
    decls: list[Decl]


def parse_outline_markdown(md: str) -> ParsedOutline:
    """Parse an ast-lens outline (Markdown) into a :class:`ParsedOutline`.

    Pure and total: malformed or partial input yields whatever was parseable
    rather than raising.
    """
    file: str | None = None
    loc: int | None = None
    decl_count: int | None = None
    doc_lines: list[str] = []
    imports: list[str] = []
    decls: list[Decl] = []
    section: str | None = None

    for raw in md.splitlines():
        line = raw.rstrip("\n")
        header = _HEADER_RE.match(line)
        if header:
            file = header.group("file").strip()
            loc = int(header.group("loc"))
            decl_count = int(header.group("decls"))
            continue
        sec = _SECTION_RE.match(line)
        if sec:
            section = sec.group("name")
            continue
        if section is None and line.startswith(">"):
            text = line.lstrip(">").strip()
            if text and text != "(truncated)":
                doc_lines.append(text)
            continue
        if section == "Imports":
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                imports.extend(
                    name.strip() for name in stripped.split(",") if name.strip()
                )
            continue
        if section in ("Types", "Functions", "Values"):
            nested = _NESTED_RE.match(line)
            if nested and decls:
                decls[-1].nested.append(
                    (
                        nested.group("label").strip(),
                        Span(int(nested.group("l0")), int(nested.group("l1"))),
                    )
                )
                continue
            if _PRIVATE_COUNT_RE.match(line):
                continue
            decl = _parse_decl(section, line)
            if decl is not None:
                decls.append(decl)

    return ParsedOutline(
        file=file,
        loc=loc,
        decl_count=decl_count,
        module_doc=" ".join(doc_lines) or None,
        imports=imports,
        decls=decls,
    )


def _parse_decl(section: str, line: str) -> Decl | None:
    if section == "Values":
        m = _VALUE_RE.match(line)
        if not m:
            return None
        return Decl(
            section=section,
            name=m.group("name").strip(),
            sig=m.group("name").strip(),
            symbol_kind=_value_kind(m.group("kind").strip()),
            span=Span(int(m.group("l0")), int(m.group("l1"))),
            private=False,
        )
    m = _DECL_RE.match(line)
    if not m:
        return None
    sig = m.group("sig").strip()
    return Decl(
        section=section,
        name=_name_from_sig(sig),
        sig=sig,
        symbol_kind=_decl_kind(section, sig),
        span=Span(int(m.group("l0")), int(m.group("l1"))),
        private=m.group("vis") == "private",
    )


_KEYWORDS = {
    "func", "function", "def", "class", "type", "interface", "enum", "struct",
    "const", "var", "let", "public", "private", "protected", "static", "async",
    "export", "default", "abstract", "final", "fn", "trait", "impl",
}
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


_GO_METHOD_RE = re.compile(r"^\s*func\s*\([^)]*\)\s*(?P<name>[A-Za-z_]\w*)")
_BEFORE_PARENS_RE = re.compile(r"(?P<name>[A-Za-z_$][\w$]*)\s*\(")


def _name_from_sig(sig: str) -> str:
    """Best-effort symbol name from a declaration's first line.

    ast-lens's outline shows a signature, not a clean machine name, for types
    and functions (only ``## Values`` carries an explicit name). The rules,
    in order: a Go-style ``func (recv) Name(...)`` receiver method; otherwise the
    identifier immediately before a parameter list; otherwise the first
    non-keyword identifier. Imperfect by construction — see ARCHITECTURE.md for
    the proposed ast-lens structured-``decls`` JSON enhancement that would make
    this exact.
    """
    s = sig.strip()
    m = _GO_METHOD_RE.match(s)
    if m:
        return m.group("name")
    m = _BEFORE_PARENS_RE.search(s)
    if m and m.group("name").lower() not in _KEYWORDS:
        return m.group("name")
    for tok in _IDENT_RE.findall(s):
        if tok.lower() not in _KEYWORDS:
            return tok
    return s or "<anonymous>"


def _decl_kind(section: str, sig: str) -> SymbolKind:
    low = sig.lower()
    if section == "Types":
        if "interface" in low:
            return SymbolKind.INTERFACE
        if "enum" in low:
            return SymbolKind.ENUM
        if "class" in low:
            return SymbolKind.CLASS
        return SymbolKind.TYPE
    # Functions: a Go-style receiver `func (r T) Name(...)` reads as a method.
    if re.search(r"\bfunc\s*\(", sig) or re.match(r"^\s*\(", sig):
        return SymbolKind.METHOD
    return SymbolKind.FUNCTION


def _value_kind(kind_word: str) -> SymbolKind:
    low = kind_word.lower()
    if low.startswith("const"):
        return SymbolKind.CONSTANT
    if low in ("var", "let", "variable"):
        return SymbolKind.VARIABLE
    return SymbolKind.OTHER


def outline_to_graph(
    parsed: ParsedOutline,
    rel_path: str,
    lang: str | None,
    graph: KnowledgeGraph,
) -> Node:
    """Add ``parsed``'s file node, symbol nodes, and edges to ``graph``.

    Returns the file node. Symbol IDs collide only when a file declares two
    same-kind, same-name symbols; the second and later are disambiguated by
    line span.
    """
    fnode = graph.add_node(
        Node(
            id=file_id(rel_path),
            kind=NodeKind.FILE,
            label=rel_path.rsplit("/", 1)[-1],
            path=rel_path,
            lang=lang,
            provenance=Provenance.AST,
            attrs={"loc": parsed.loc} if parsed.loc is not None else {},
        )
    )
    if parsed.module_doc:
        fnode.attrs.setdefault("module_doc", parsed.module_doc)

    seen: set[str] = set()
    for decl in parsed.decls:
        base = symbol_id(rel_path, decl.symbol_kind, decl.name)
        sid = base
        if sid in seen:
            sid = f"{base}@{decl.span.start_line}-{decl.span.end_line}"
        seen.add(sid)
        graph.add_node(
            Node(
                id=sid,
                kind=NodeKind.SYMBOL,
                label=decl.name,
                path=rel_path,
                lang=lang,
                span=decl.span,
                provenance=Provenance.AST,
                attrs={
                    "symbol_kind": decl.symbol_kind.value,
                    "signature": decl.sig,
                    "private": decl.private,
                },
            )
        )
        graph.add_edge(
            Edge(src=fnode.id, dst=sid, kind=EdgeKind.CONTAINS, provenance=Provenance.AST)
        )

    for mod in dict.fromkeys(parsed.imports):  # dedup, preserve order
        iid = import_id(rel_path, mod)
        graph.add_node(
            Node(
                id=iid,
                kind=NodeKind.IMPORT,
                label=mod,
                path=rel_path,
                provenance=Provenance.AST,
                attrs={"module": mod},
            )
        )
        graph.add_edge(
            Edge(src=fnode.id, dst=iid, kind=EdgeKind.IMPORTS, provenance=Provenance.AST)
        )

    return fnode


def run_outline(
    abs_path: str,
    *,
    budget: int = 300,
    threshold: int = 0,
    binary: str | None = None,
    timeout: float = 30.0,
) -> ParsedOutline | None:
    """Run the ast-lens ``outline`` CLI on ``abs_path`` and parse its output.

    Returns ``None`` (never raises) when ast-lens is not installed, the file is
    passed through (empty output), or the call fails — so a corpus build still
    yields filesystem-level nodes even where ast-lens is unavailable.

    ``binary`` defaults to ``$AST_LENS_BIN`` then ``outline`` on ``PATH``. A
    ``threshold`` of ``0`` asks ast-lens to emit even for small files.
    """
    exe = binary or os.environ.get("AST_LENS_BIN") or shutil.which("outline")
    if not exe:
        return None
    cmd = [exe, abs_path, "--format", "json", "--budget", str(budget), "--threshold", str(threshold)]
    try:
        proc = subprocess.run(  # noqa: S603 - explicit argv, no shell
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    try:
        envelope = json.loads(out)
    except json.JSONDecodeError:
        return None
    md = envelope.get("markdown", "")
    if not md:
        return None
    parsed = parse_outline_markdown(md)
    if parsed.file is None and not parsed.decls:
        return None
    if envelope.get("file") and parsed.file is None:
        parsed.file = envelope["file"]
    return parsed
