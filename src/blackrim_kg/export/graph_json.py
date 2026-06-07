"""The canonical node-link JSON export.

This is the portable artifact you keep and re-query without re-parsing the
corpus. It is deterministic — nodes and edges are emitted in sorted order and
serialized with sorted keys — so committing ``kg-out/graph.json`` to a repo
yields small, reviewable diffs as the project changes.
"""

from __future__ import annotations

import json

from .. import SCHEMA, __version__
from ..graph import KnowledgeGraph


def to_json_obj(graph: KnowledgeGraph, *, root: str | None = None) -> dict:
    """Serialize ``graph`` to a plain dict ready for ``json.dump``."""
    body = graph.to_dict()
    return {
        "schema": SCHEMA,
        "schema_version": __version__,
        "root": root,
        "stats": graph.stats(),
        "nodes": body["nodes"],
        "edges": body["edges"],
    }


def to_json(graph: KnowledgeGraph, *, root: str | None = None, indent: int = 2) -> str:
    return json.dumps(to_json_obj(graph, root=root), indent=indent, sort_keys=True)


def dump_json(
    graph: KnowledgeGraph, out_path: str, *, root: str | None = None, indent: int = 2
) -> None:
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(to_json(graph, root=root, indent=indent))
        fh.write("\n")


def load_json(in_path: str) -> KnowledgeGraph:
    with open(in_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return KnowledgeGraph.from_dict(data)
