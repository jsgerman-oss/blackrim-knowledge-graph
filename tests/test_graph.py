"""Graph container: dedup, merge, adjacency, traversal, serialization."""

from __future__ import annotations

import pytest

from blackrim_kg.graph import KnowledgeGraph
from blackrim_kg.model import Edge, EdgeKind, Node, NodeKind, Provenance, Span


def _file(fid: str, **kw) -> Node:
    return Node(id=fid, kind=NodeKind.FILE, label=fid, **kw)


def _sym(sid: str) -> Node:
    return Node(id=sid, kind=NodeKind.SYMBOL, label=sid)


def test_add_node_is_idempotent_and_merges_attrs():
    g = KnowledgeGraph()
    g.add_node(_file("file:a.py", attrs={"loc": 10}))
    # Re-add with a span and another attr; identity stays, fields fill in.
    merged = g.add_node(_file("file:a.py", span=Span(1, 9), attrs={"author": "x"}))
    assert g.node_count() == 1
    assert merged.span == Span(1, 9)
    assert merged.attrs == {"loc": 10, "author": "x"}


def test_add_edge_dedups_by_identity_tuple():
    g = KnowledgeGraph()
    g.add_node(_file("file:a.py"))
    g.add_node(_sym("sym:a.py#function:f"))
    e = Edge("file:a.py", "sym:a.py#function:f", EdgeKind.CONTAINS)
    g.add_edge(e)
    g.add_edge(Edge("file:a.py", "sym:a.py#function:f", EdgeKind.CONTAINS))
    assert g.edge_count() == 1


def test_add_edge_requires_existing_endpoints():
    g = KnowledgeGraph()
    g.add_node(_file("file:a.py"))
    with pytest.raises(KeyError):
        g.add_edge(Edge("file:a.py", "missing", EdgeKind.CONTAINS))


def test_neighbors_directionality():
    g = KnowledgeGraph()
    g.add_node(_file("file:a.py"))
    g.add_node(_sym("sym:f"))
    g.add_edge(Edge("file:a.py", "sym:f", EdgeKind.CONTAINS))
    assert [n.id for n in g.neighbors("file:a.py", direction="out")] == ["sym:f"]
    assert g.neighbors("file:a.py", direction="in") == []
    assert [n.id for n in g.neighbors("sym:f", direction="in")] == ["file:a.py"]


def test_shortest_path_directed_and_undirected():
    g = KnowledgeGraph()
    for nid in ("a", "b", "c"):
        g.add_node(Node(id=nid, kind=NodeKind.SYMBOL, label=nid))
    g.add_edge(Edge("a", "b", EdgeKind.CALLS))
    g.add_edge(Edge("b", "c", EdgeKind.CALLS))
    assert g.shortest_path("a", "c") == ["a", "b", "c"]
    assert g.shortest_path("c", "a") is None  # no directed path back
    assert g.shortest_path("c", "a", directed=False) == ["c", "b", "a"]
    assert g.shortest_path("a", "a") == ["a"]


def test_stats_counts_by_kind_and_provenance():
    g = KnowledgeGraph()
    g.add_node(_file("file:a.py", provenance=Provenance.AST))
    g.add_node(_sym("sym:f"))
    g.add_edge(Edge("file:a.py", "sym:f", EdgeKind.CONTAINS))
    stats = g.stats()
    assert stats["node_count"] == 2
    assert stats["nodes_by_kind"] == {"file": 1, "symbol": 1}
    assert stats["edges_by_kind"] == {"contains": 1}


def test_serialization_round_trip():
    g = KnowledgeGraph()
    g.add_node(_file("file:a.py"))
    g.add_node(_sym("sym:f"))
    g.add_edge(Edge("file:a.py", "sym:f", EdgeKind.CONTAINS))
    restored = KnowledgeGraph.from_dict(g.to_dict())
    assert restored.to_dict() == g.to_dict()


def test_iteration_is_sorted():
    g = KnowledgeGraph()
    for nid in ("file:c", "file:a", "file:b"):
        g.add_node(_file(nid))
    assert [n.id for n in g.nodes()] == ["file:a", "file:b", "file:c"]
