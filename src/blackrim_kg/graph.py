"""The in-memory knowledge-graph container.

A deliberately small, dependency-free graph. The scaffold keeps its own
adjacency index rather than reaching for ``networkx`` so the core engine runs
under any ``python3`` (matching the sibling gas-town packs). The optional
``algorithms`` extra layers ``networkx`` on top for centrality and community
detection at scale — see ARCHITECTURE.md §"Stack" — but nothing here requires it.

Design notes:

- **Idempotent node insertion with attribute merge.** Re-adding a node id keeps
  the first node's identity and fills in any attributes/fields the later copy
  supplies but the first omitted. This lets independent sources (the
  filesystem walker, the ast-lens adapter, a docs pass) each contribute partial
  knowledge about the same node without clobbering one another.
- **Edge dedup by identity tuple** (``src, dst, kind, provenance``) so re-runs
  and overlapping sources do not inflate degree.
- **Deterministic iteration.** Nodes and edges always iterate in sorted order so
  exports diff cleanly in git.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator

from .model import Edge, EdgeKind, Node, NodeKind


class KnowledgeGraph:
    """A directed, typed multi-relation graph keyed by stable node IDs."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[tuple[str, str, str, str], Edge] = {}
        self._out: dict[str, list[tuple[str, str, str, str]]] = {}
        self._in: dict[str, list[tuple[str, str, str, str]]] = {}

    # --- mutation -----------------------------------------------------------

    def add_node(self, node: Node) -> Node:
        """Insert ``node``, or merge it into an existing node with the same id.

        Returns the canonical stored node. Existing scalar fields win; missing
        ones are filled from ``node``; ``attrs`` are merged (existing wins).
        """
        existing = self._nodes.get(node.id)
        if existing is None:
            self._nodes[node.id] = node
            self._out.setdefault(node.id, [])
            self._in.setdefault(node.id, [])
            return node
        for f in ("label", "path", "lang", "span"):
            if getattr(existing, f) in (None, "") and getattr(node, f) not in (None, ""):
                setattr(existing, f, getattr(node, f))
        for k, v in node.attrs.items():
            existing.attrs.setdefault(k, v)
        return existing

    def add_edge(self, edge: Edge) -> Edge:
        """Insert ``edge`` (deduped by identity tuple). Endpoints must exist."""
        if edge.src not in self._nodes:
            raise KeyError(f"edge source not in graph: {edge.src}")
        if edge.dst not in self._nodes:
            raise KeyError(f"edge target not in graph: {edge.dst}")
        key = edge.key()
        if key in self._edges:
            return self._edges[key]
        self._edges[key] = edge
        self._out[edge.src].append(key)
        self._in[edge.dst].append(key)
        return edge

    # --- lookup -------------------------------------------------------------

    def get(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def nodes(self, kind: NodeKind | None = None) -> Iterator[Node]:
        for nid in sorted(self._nodes):
            node = self._nodes[nid]
            if kind is None or node.kind == kind:
                yield node

    def edges(self, kind: EdgeKind | None = None) -> Iterator[Edge]:
        for key in sorted(self._edges):
            edge = self._edges[key]
            if kind is None or edge.kind == kind:
                yield edge

    def out_edges(self, node_id: str, kinds: Iterable[EdgeKind] | None = None) -> list[Edge]:
        allow = set(kinds) if kinds is not None else None
        out = [self._edges[k] for k in self._out.get(node_id, [])]
        if allow is not None:
            out = [e for e in out if e.kind in allow]
        return sorted(out, key=lambda e: e.key())

    def in_edges(self, node_id: str, kinds: Iterable[EdgeKind] | None = None) -> list[Edge]:
        allow = set(kinds) if kinds is not None else None
        ins = [self._edges[k] for k in self._in.get(node_id, [])]
        if allow is not None:
            ins = [e for e in ins if e.kind in allow]
        return sorted(ins, key=lambda e: e.key())

    def degree(self, node_id: str) -> int:
        return len(self._out.get(node_id, [])) + len(self._in.get(node_id, []))

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    # --- analysis -----------------------------------------------------------

    def stats(self) -> dict:
        """Return counts by node kind, edge kind, provenance, and confidence."""
        nodes_by_kind: dict[str, int] = {}
        node_provenance: dict[str, int] = {}
        for n in self._nodes.values():
            nodes_by_kind[n.kind.value] = nodes_by_kind.get(n.kind.value, 0) + 1
            node_provenance[n.provenance.value] = node_provenance.get(n.provenance.value, 0) + 1
        edges_by_kind: dict[str, int] = {}
        edge_confidence: dict[str, int] = {}
        for e in self._edges.values():
            edges_by_kind[e.kind.value] = edges_by_kind.get(e.kind.value, 0) + 1
            edge_confidence[e.confidence.value] = edge_confidence.get(e.confidence.value, 0) + 1
        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "nodes_by_kind": dict(sorted(nodes_by_kind.items())),
            "edges_by_kind": dict(sorted(edges_by_kind.items())),
            "node_provenance": dict(sorted(node_provenance.items())),
            "edge_confidence": dict(sorted(edge_confidence.items())),
        }

    def neighbors(
        self,
        node_id: str,
        *,
        direction: str = "out",
        kinds: Iterable[EdgeKind] | None = None,
    ) -> list[Node]:
        """Return adjacent nodes. ``direction`` is ``out``, ``in``, or ``both``."""
        seen: dict[str, None] = {}
        if direction in ("out", "both"):
            for e in self.out_edges(node_id, kinds):
                seen.setdefault(e.dst, None)
        if direction in ("in", "both"):
            for e in self.in_edges(node_id, kinds):
                seen.setdefault(e.src, None)
        return [self._nodes[n] for n in sorted(seen) if n in self._nodes]

    def shortest_path(
        self, src: str, dst: str, *, directed: bool = True
    ) -> list[str] | None:
        """Breadth-first shortest path of node IDs from ``src`` to ``dst``."""
        if src not in self._nodes or dst not in self._nodes:
            return None
        if src == dst:
            return [src]
        prev: dict[str, str | None] = {src: None}
        q: deque[str] = deque([src])
        while q:
            cur = q.popleft()
            adj = [e.dst for e in self.out_edges(cur)]
            if not directed:
                adj += [e.src for e in self.in_edges(cur)]
            for nxt in sorted(set(adj)):
                if nxt not in prev:
                    prev[nxt] = cur
                    if nxt == dst:
                        return _reconstruct(prev, dst)
                    q.append(nxt)
        return None

    # --- serialization ------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes()],
            "edges": [e.to_dict() for e in self.edges()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> KnowledgeGraph:
        g = cls()
        for nd in d.get("nodes", []):
            g.add_node(Node.from_dict(nd))
        for ed in d.get("edges", []):
            g.add_edge(Edge.from_dict(ed))
        return g


def _reconstruct(prev: dict[str, str | None], dst: str) -> list[str]:
    path: list[str] = []
    cur: str | None = dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path
