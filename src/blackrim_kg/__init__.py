"""blackrim_kg — an AST-first, queryable knowledge graph for a project.

The engine turns a corpus (source code first, documentation and other
artifacts next) into a typed, directed graph that you keep and query, rather
than re-deriving with grep on every question. Precise structure comes from the
``ast-lens`` pack (symbols, containment, imports); enrichment layers (reference
and call edges, documentation, semantic concepts) sit cleanly on top and are
always provenance-tagged, so the exact spine is never confused with inference.

Public surface (what the CLI and downstream tools build on):

- :mod:`blackrim_kg.model`   — the node/edge taxonomy (:class:`~blackrim_kg.model.Node`,
  :class:`~blackrim_kg.model.Edge`, and the ``NodeKind`` / ``EdgeKind`` /
  ``Provenance`` / ``Confidence`` enums) plus stable-ID helpers.
- :mod:`blackrim_kg.graph`   — the in-memory :class:`~blackrim_kg.graph.KnowledgeGraph`
  container with adjacency, dedup, and deterministic serialization.
- :mod:`blackrim_kg.astlens` — the ast-lens adapter: run the ``outline`` CLI and
  parse its outline schema into graph nodes and edges.
- :mod:`blackrim_kg.build`   — the :class:`~blackrim_kg.build.GraphBuilder` that
  walks a corpus and assembles a graph from its sources.
- :mod:`blackrim_kg.query`   — neighbourhood, path, dependency, and search queries.
- :mod:`blackrim_kg.export`  — the JSON, HTML, and markdown-report exporters.
- :mod:`blackrim_kg.cli`     — the ``kg`` command.
"""

from __future__ import annotations

SCHEMA = "blackrim_kg.v0"
__version__ = "0.1.0"

__all__ = ["SCHEMA", "__version__"]
