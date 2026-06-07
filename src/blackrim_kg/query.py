"""Queries over a built knowledge graph.

These are the questions a graph exists to answer cheaply — "what is this", "what
does it touch", "what touches it", "how do these two connect" — expressed
against the :class:`~blackrim_kg.graph.KnowledgeGraph` container. They are thin,
deterministic, and dependency-free; richer ranked queries (centrality-weighted
neighbourhoods, semantic search) belong to the analysis layer and the optional
``algorithms`` extra.
"""

from __future__ import annotations

from .graph import KnowledgeGraph
from .model import EdgeKind, Node, NodeKind

# Edges that express a forward dependency: A -> B means "A depends on B".
_DEPENDENCY_EDGES = (
    EdgeKind.IMPORTS,
    EdgeKind.CALLS,
    EdgeKind.REFERENCES,
    EdgeKind.INHERITS,
    EdgeKind.IMPLEMENTS,
)


def search(graph: KnowledgeGraph, text: str, *, kind: NodeKind | None = None) -> list[Node]:
    """Case-insensitive substring match over node labels and IDs."""
    needle = text.lower()
    hits = [
        n
        for n in graph.nodes(kind)
        if needle in n.label.lower() or needle in n.id.lower()
    ]
    return hits


def neighbors(
    graph: KnowledgeGraph,
    node_id: str,
    *,
    direction: str = "both",
    edge_kinds: list[EdgeKind] | None = None,
) -> list[Node]:
    """Adjacent nodes in the given direction (``out`` / ``in`` / ``both``)."""
    return graph.neighbors(node_id, direction=direction, kinds=edge_kinds)


def path(
    graph: KnowledgeGraph, src: str, dst: str, *, directed: bool = True
) -> list[Node] | None:
    """Shortest path between two nodes, returned as a node list (or ``None``)."""
    ids = graph.shortest_path(src, dst, directed=directed)
    if ids is None:
        return None
    return [graph.get(i) for i in ids if graph.get(i) is not None]


def dependencies(graph: KnowledgeGraph, node_id: str) -> list[Node]:
    """What ``node_id`` depends on (forward over import/call/reference edges)."""
    return graph.neighbors(node_id, direction="out", kinds=_DEPENDENCY_EDGES)


def dependents(graph: KnowledgeGraph, node_id: str) -> list[Node]:
    """What depends on ``node_id`` (reverse over import/call/reference edges)."""
    return graph.neighbors(node_id, direction="in", kinds=_DEPENDENCY_EDGES)


def explain(graph: KnowledgeGraph, node_id: str) -> dict | None:
    """A compact, self-contained description of a node and its neighbourhood."""
    node = graph.get(node_id)
    if node is None:
        return None
    out_groups: dict[str, list[str]] = {}
    for e in graph.out_edges(node_id):
        out_groups.setdefault(e.kind.value, []).append(e.dst)
    in_groups: dict[str, list[str]] = {}
    for e in graph.in_edges(node_id):
        in_groups.setdefault(e.kind.value, []).append(e.src)
    return {
        "node": node.to_dict(),
        "degree": graph.degree(node_id),
        "out": {k: sorted(v) for k, v in sorted(out_groups.items())},
        "in": {k: sorted(v) for k, v in sorted(in_groups.items())},
    }


def most_connected(
    graph: KnowledgeGraph, *, top_n: int = 20, kind: NodeKind | None = None
) -> list[tuple[Node, int]]:
    """Nodes ranked by raw degree centrality (the spine's "hub" symbols).

    Degree is the cheap, exact centrality the scaffold ships; weighted and
    community-aware ranking is part of the analysis layer (``algorithms`` extra).
    """
    ranked = [
        (n, graph.degree(n.id))
        for n in graph.nodes(kind)
    ]
    ranked.sort(key=lambda pair: (-pair[1], pair[0].id))
    return ranked[:top_n]
