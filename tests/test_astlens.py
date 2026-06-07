"""ast-lens adapter: outline-schema parsing, name derivation, graph mapping."""

from __future__ import annotations

from blackrim_kg.astlens import (
    outline_to_graph,
    parse_outline_markdown,
    run_outline,
)
from blackrim_kg.graph import KnowledgeGraph
from blackrim_kg.model import EdgeKind, NodeKind, Span, SymbolKind

# A representative ast-lens outline. Line spans use the EN DASH (U+2013) exactly
# as ast-lens renders them; – keeps the fixture unambiguous in source.
OUTLINE = (
    "# store.go (233 LoC, 6 decls)\n"
    "\n"
    "> Package store provides session storage.\n"
    "\n"
    "## Imports\n"
    "errors, fmt, sync, time\n"
    "\n"
    "## Types\n"
    "- `type Session struct` (L28–34)\n"
    "- `type Store interface` *(private)* (L40–52)\n"
    "  - Get (L41–43)\n"
    "\n"
    "## Functions\n"
    "- `func New() *Store` (L60–70)\n"
    "- `func (s *Store) Get(id string) (*Session, error)` (L72–95)\n"
    "\n"
    "## Values\n"
    "- `DefaultTTL` (const, L10–10)\n"
    "- `mu` (var, L12–12)\n"
)


def _by_name(decls):
    return {d.name: d for d in decls}


def test_parse_header_doc_and_imports():
    p = parse_outline_markdown(OUTLINE)
    assert p.file == "store.go"
    assert p.loc == 233
    assert p.decl_count == 6
    assert p.module_doc == "Package store provides session storage."
    assert p.imports == ["errors", "fmt", "sync", "time"]


def test_parse_decls_kinds_visibility_and_spans():
    p = parse_outline_markdown(OUTLINE)
    decls = _by_name(p.decls)
    assert set(decls) == {"Session", "Store", "New", "Get", "DefaultTTL", "mu"}

    assert decls["Session"].symbol_kind is SymbolKind.TYPE
    assert decls["Session"].span == Span(28, 34)

    assert decls["Store"].symbol_kind is SymbolKind.INTERFACE
    assert decls["Store"].private is True
    assert decls["Store"].nested == [("Get", Span(41, 43))]

    assert decls["New"].symbol_kind is SymbolKind.FUNCTION
    assert decls["Get"].symbol_kind is SymbolKind.METHOD  # Go receiver method
    assert decls["DefaultTTL"].symbol_kind is SymbolKind.CONSTANT
    assert decls["mu"].symbol_kind is SymbolKind.VARIABLE


def test_parser_accepts_plain_hyphen_spans():
    p = parse_outline_markdown(
        "# a.py (5 LoC, 1 decls)\n\n## Functions\n- `def f()` (L1-3)\n"
    )
    assert p.decls and p.decls[0].span == Span(1, 3)
    assert p.decls[0].name == "f"


def test_parse_empty_is_total_not_raising():
    p = parse_outline_markdown("")
    assert p.file is None and p.decls == [] and p.imports == []


def test_outline_to_graph_builds_spine():
    p = parse_outline_markdown(OUTLINE)
    g = KnowledgeGraph()
    fnode = outline_to_graph(p, "pkg/store.go", "go", g)

    assert fnode.kind is NodeKind.FILE
    assert fnode.id == "file:pkg/store.go"
    assert fnode.attrs["loc"] == 233
    assert fnode.attrs["module_doc"].startswith("Package store")

    symbols = list(g.nodes(NodeKind.SYMBOL))
    assert len(symbols) == 6
    assert "sym:pkg/store.go#method:Get" in g
    assert "sym:pkg/store.go#interface:Store" in g

    contains = list(g.edges(EdgeKind.CONTAINS))
    assert len(contains) == 6
    assert all(e.src == fnode.id for e in contains)

    imports = list(g.nodes(NodeKind.IMPORT))
    assert len(imports) == 4
    assert len(list(g.edges(EdgeKind.IMPORTS))) == 4


def test_symbol_id_collisions_disambiguate_by_span():
    md = (
        "# a.py (20 LoC, 2 decls)\n\n## Functions\n"
        "- `def f()` (L1–3)\n"
        "- `def f()` (L8–10)\n"
    )
    g = KnowledgeGraph()
    outline_to_graph(parse_outline_markdown(md), "a.py", "python", g)
    syms = [n.id for n in g.nodes(NodeKind.SYMBOL)]
    assert "sym:a.py#function:f" in syms
    assert "sym:a.py#function:f@8-10" in syms


def test_run_outline_returns_none_when_binary_absent():
    # A bogus path makes subprocess raise; the adapter swallows it and yields None.
    assert run_outline("whatever.py", binary="/nonexistent/outline-binary") is None
