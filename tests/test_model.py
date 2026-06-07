"""Model: ID stability, serialization round-trips, enum integrity."""

from __future__ import annotations

from blackrim_kg.model import (
    Confidence,
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    Provenance,
    Span,
    SymbolKind,
    disambiguate,
    file_id,
    import_id,
    module_id,
    normalize_path,
    symbol_id,
)


def test_normalize_path_is_portable():
    assert normalize_path("a\\b\\c.py") == "a/b/c.py"
    assert normalize_path("./pkg/mod.py") == "pkg/mod.py"
    assert normalize_path("pkg/../pkg/mod.py") == "pkg/mod.py"


def test_id_helpers_are_stable_and_scheme_prefixed():
    assert file_id("src/app.py") == "file:src/app.py"
    assert symbol_id("src/app.py", SymbolKind.FUNCTION, "main") == "sym:src/app.py#function:main"
    assert symbol_id("src/app.py", "class", "App") == "sym:src/app.py#class:App"
    assert import_id("src/app.py", "os") == "imp:src/app.py->os"
    assert module_id("a\\b") == "mod:a/b"


def test_disambiguate_only_appends_with_span():
    base = "sym:a.py#function:f"
    assert disambiguate(base, None) == base
    assert disambiguate(base, Span(3, 9)) == f"{base}@3-9"


def test_node_round_trip_preserves_fields():
    n = Node(
        id="sym:a.py#function:f",
        kind=NodeKind.SYMBOL,
        label="f",
        path="a.py",
        lang="python",
        span=Span(1, 4),
        provenance=Provenance.AST,
        attrs={"symbol_kind": "function", "private": False},
    )
    restored = Node.from_dict(n.to_dict())
    assert restored == n


def test_node_to_dict_omits_empty_optionals():
    n = Node(id="file:a.py", kind=NodeKind.FILE, label="a.py")
    d = n.to_dict()
    assert "path" not in d and "lang" not in d and "span" not in d and "attrs" not in d


def test_edge_round_trip_and_key():
    e = Edge(
        src="file:a.py",
        dst="sym:a.py#function:f",
        kind=EdgeKind.CONTAINS,
        provenance=Provenance.AST,
        confidence=Confidence.EXACT,
        weight=2.0,
        attrs={"note": "x"},
    )
    restored = Edge.from_dict(e.to_dict())
    assert restored == e
    assert e.key() == ("file:a.py", "sym:a.py#function:f", "contains", "ast")
