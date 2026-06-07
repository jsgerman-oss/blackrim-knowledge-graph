"""Exporters: deterministic JSON, report sections, self-contained safe HTML."""

from __future__ import annotations

import json

from blackrim_kg.export import render_html, render_report
from blackrim_kg.export.graph_json import to_json
from blackrim_kg.graph import KnowledgeGraph
from blackrim_kg.model import Edge, EdgeKind, Node, NodeKind, Span, SymbolKind


def _graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add_node(Node(id="file:a.py", kind=NodeKind.FILE, label="a.py", lang="python"))
    g.add_node(
        Node(
            id="sym:a.py#function:main",
            kind=NodeKind.SYMBOL,
            label="main",
            path="a.py",
            span=Span(1, 4),
            attrs={"symbol_kind": SymbolKind.FUNCTION.value},
        )
    )
    g.add_edge(Edge("file:a.py", "sym:a.py#function:main", EdgeKind.CONTAINS))
    return g


def test_json_is_deterministic_and_round_trips():
    g = _graph()
    a = to_json(g, root="/x")
    b = to_json(g, root="/x")
    assert a == b  # stable across calls
    obj = json.loads(a)
    assert obj["root"] == "/x"
    assert obj["schema_version"]
    assert obj["stats"]["node_count"] == 2
    restored = KnowledgeGraph.from_dict(obj)
    assert restored.to_dict() == g.to_dict()


def test_report_has_expected_sections():
    text = render_report(_graph(), root="/x")
    assert text.startswith("# Knowledge Graph Report")
    assert "## Summary" in text
    assert "Most connected symbols" in text
    assert "`main`" in text
    assert "## Files" in text
    # A flat corpus (file at root) has no directory boundaries.
    assert "## Module boundaries (0)" in text


def test_report_lists_module_boundaries():
    g = KnowledgeGraph()
    g.add_node(Node(id="mod:src", kind=NodeKind.MODULE, label="src", path="src"))
    g.add_node(Node(id="file:src/a.py", kind=NodeKind.FILE, label="a.py", path="src/a.py"))
    g.add_node(Node(id="file:src/b.py", kind=NodeKind.FILE, label="b.py", path="src/b.py"))
    g.add_edge(Edge("mod:src", "file:src/a.py", EdgeKind.CONTAINS))
    g.add_edge(Edge("mod:src", "file:src/b.py", EdgeKind.CONTAINS))

    text = render_report(g)
    assert "## Module boundaries (1)" in text
    assert "| `src` | 2 |" in text


def test_html_is_self_contained_and_embeds_data():
    html = render_html(_graph(), title="Demo", root="/x")
    assert html.startswith("<!DOCTYPE html>")
    assert 'id="kg-graph"' in html  # embedded data island
    assert "main" in html
    # The embedded JSON payload is present and parseable.
    start = html.index('id="kg-graph">') + len('id="kg-graph">')
    end = html.index("</script>", start)
    payload = json.loads(html[start:end].replace("<\\/", "</"))
    assert payload["stats"]["node_count"] == 2


def test_html_escapes_script_close_in_data():
    g = KnowledgeGraph()
    g.add_node(Node(id="x", kind=NodeKind.CONCEPT, label="danger</script>boom"))
    html = render_html(g)
    # The literal "</script>" from data must be neutralised in the data island.
    assert "danger<\\/script>boom" in html
