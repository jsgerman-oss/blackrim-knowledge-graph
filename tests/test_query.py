"""Queries: search, neighbours, path, dependency direction, explain, ranking."""

from __future__ import annotations

import pytest

from blackrim_kg.graph import KnowledgeGraph
from blackrim_kg.model import Edge, EdgeKind, Node, NodeKind
from blackrim_kg.query import (
    dependencies,
    dependents,
    explain,
    most_connected,
    neighbors,
    path,
    search,
)


@pytest.fixture
def g() -> KnowledgeGraph:
    kg = KnowledgeGraph()
    kg.add_node(Node(id="file:a.py", kind=NodeKind.FILE, label="a.py"))
    kg.add_node(Node(id="sym:a.py#function:main", kind=NodeKind.SYMBOL, label="main"))
    kg.add_node(Node(id="sym:a.py#function:helper", kind=NodeKind.SYMBOL, label="helper"))
    kg.add_node(Node(id="imp:a.py->os", kind=NodeKind.IMPORT, label="os"))
    kg.add_edge(Edge("file:a.py", "sym:a.py#function:main", EdgeKind.CONTAINS))
    kg.add_edge(Edge("file:a.py", "sym:a.py#function:helper", EdgeKind.CONTAINS))
    kg.add_edge(Edge("file:a.py", "imp:a.py->os", EdgeKind.IMPORTS))
    kg.add_edge(Edge("sym:a.py#function:main", "sym:a.py#function:helper", EdgeKind.CALLS))
    return kg


def test_search_matches_label_and_id(g):
    assert {n.id for n in search(g, "helper")} == {"sym:a.py#function:helper"}
    # id substring also matches
    assert any(n.id == "imp:a.py->os" for n in search(g, "->os"))


def test_search_filter_by_kind(g):
    hits = search(g, "a.py", kind=NodeKind.FILE)
    assert [n.id for n in hits] == ["file:a.py"]


def test_neighbors_both_directions(g):
    out = {n.id for n in neighbors(g, "file:a.py", direction="out")}
    assert out == {"sym:a.py#function:main", "sym:a.py#function:helper", "imp:a.py->os"}


def test_dependencies_vs_dependents(g):
    # main depends on helper (calls); helper is depended-on by main.
    assert [n.id for n in dependencies(g, "sym:a.py#function:main")] == [
        "sym:a.py#function:helper"
    ]
    assert [n.id for n in dependents(g, "sym:a.py#function:helper")] == [
        "sym:a.py#function:main"
    ]
    # The file's only dependency is its import; CONTAINS edges to the symbols
    # it holds are not dependencies and must be filtered out.
    assert [n.id for n in dependencies(g, "file:a.py")] == ["imp:a.py->os"]


def test_path_returns_node_chain(g):
    # file -> helper is a direct CONTAINS edge, so BFS returns the 2-node path.
    chain = path(g, "file:a.py", "sym:a.py#function:helper")
    assert chain is not None
    assert [n.id for n in chain] == ["file:a.py", "sym:a.py#function:helper"]
    # main -> helper is the only path via calls when starting at main.
    via_call = path(g, "sym:a.py#function:main", "sym:a.py#function:helper")
    assert [n.id for n in via_call] == [
        "sym:a.py#function:main",
        "sym:a.py#function:helper",
    ]


def test_explain_groups_neighbours(g):
    info = explain(g, "file:a.py")
    assert info["degree"] == 3
    assert set(info["out"]["contains"]) == {
        "sym:a.py#function:main",
        "sym:a.py#function:helper",
    }
    assert info["out"]["imports"] == ["imp:a.py->os"]
    assert explain(g, "missing") is None


def test_most_connected_ranks_by_degree(g):
    # main and helper both have degree 2; ties break by id, so helper sorts first.
    ranked = most_connected(g, kind=NodeKind.SYMBOL)
    assert [(n.id, d) for n, d in ranked] == [
        ("sym:a.py#function:helper", 2),
        ("sym:a.py#function:main", 2),
    ]
    # the file is the top hub overall with degree 3 (two symbols + one import).
    top = most_connected(g)
    assert top[0][0].id == "file:a.py"
    assert top[0][1] == 3
