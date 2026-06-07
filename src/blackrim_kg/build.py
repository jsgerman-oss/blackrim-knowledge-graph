"""Assemble a :class:`~blackrim_kg.graph.KnowledgeGraph` from a project corpus.

The builder orchestrates the *spine*: walk the corpus, run ast-lens per code
file, fold each outline into the graph as file/symbol/import nodes with
``contains`` and ``imports`` edges, and finally derive the ``module`` boundary
nodes that the per-file outline has no notion of (directory/package structure),
so the containment spine runs the whole way down — ``module -> file -> symbol``.
The enrichment layers the architecture defines — import resolution (coarse
import names -> concrete file/module nodes), reference and call edges,
documentation, and semantic concepts — attach after the spine exists and are
intentionally left as follow-up work (see ARCHITECTURE.md §"Implementation
roadmap").

The ast-lens call is injected as ``outline_fn`` so the builder is testable
without ast-lens installed and so alternative structure sources can be swapped
in. When ast-lens is unavailable, ``outline_fn`` returns ``None`` and the build
still records a filesystem-level file node per source file.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable

from .astlens import ParsedOutline, outline_to_graph, run_outline
from .graph import KnowledgeGraph
from .model import (
    Confidence,
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    Provenance,
    file_id,
    module_id,
)
from .sources import DiscoveredFile, FilesystemWalker

OutlineFn = Callable[[DiscoveredFile], "ParsedOutline | None"]


class GraphBuilder:
    """Build a knowledge graph for the project rooted at ``root``."""

    def __init__(
        self,
        root: str,
        *,
        outline_fn: OutlineFn | None = None,
        budget: int = 300,
        threshold: int = 0,
        include_docs: bool = False,
    ) -> None:
        self.root = root
        self.budget = budget
        self.threshold = threshold
        self.include_docs = include_docs
        self.outline_fn = outline_fn or self._default_outline

    def _default_outline(self, f: DiscoveredFile) -> ParsedOutline | None:
        return run_outline(f.abs_path, budget=self.budget, threshold=self.threshold)

    def build(self) -> KnowledgeGraph:
        graph = KnowledgeGraph()
        walker = FilesystemWalker(self.root, include_docs=self.include_docs)
        for f in walker:
            if f.category != "code":
                # Documentation ingestion is a follow-up; record a bare file node
                # so the corpus is represented even before the docs source lands.
                graph.add_node(
                    Node(
                        id=file_id(f.rel_path),
                        kind=NodeKind.FILE,
                        label=f.rel_path.rsplit("/", 1)[-1],
                        path=f.rel_path,
                        lang=f.lang,
                        provenance=Provenance.FS,
                    )
                )
                continue
            parsed = self.outline_fn(f)
            if parsed is None:
                # ast-lens passed the file through (small/unsupported) or is not
                # installed: keep a filesystem-provenance file node so downstream
                # resolution and queries still see the file.
                graph.add_node(
                    Node(
                        id=file_id(f.rel_path),
                        kind=NodeKind.FILE,
                        label=f.rel_path.rsplit("/", 1)[-1],
                        path=f.rel_path,
                        lang=f.lang,
                        provenance=Provenance.FS,
                    )
                )
                continue
            outline_to_graph(parsed, f.rel_path, f.lang, graph)
        # All files are in the graph; derive the directory/package boundaries
        # they sit in so the containment spine runs module -> file -> symbol.
        add_module_boundaries(graph)
        return graph


def add_module_boundaries(graph: KnowledgeGraph) -> None:
    """Synthesize ``module`` nodes for the corpus's directory/package structure.

    ast-lens emits per-file structure; it has no notion of the directory and
    package boundaries those files sit in. This pass derives that boundary layer
    from the file paths already in the graph: for each file under a directory it
    ensures a ``module`` node exists for every ancestor directory and adds the
    ``contains`` edges forming the hierarchy ``module -> submodule -> file``.

    Module structure is filesystem-exact, so these nodes and edges are
    ``provenance=fs`` / ``confidence=exact`` — distinct from the ``provenance=ast``
    ``contains`` edges the ast-lens adapter lays down from file to symbol, and so
    they never collide on the edge identity tuple. The module IDs use the
    directory *path* form (``mod:src/blackrim_kg``); mapping a path to a language's
    *dotted* module name is deterministic cross-file resolution and belongs to the
    Layer 1 import-resolution follow-up (ARCHITECTURE.md §"Implementation
    roadmap"), which will point ``imports`` edges at exactly these nodes.

    Top-level files (no parent directory) get no module node — the pass invents no
    synthetic root. Idempotent: safe to re-run on a graph that already has modules.
    """
    for fnode in list(graph.nodes(NodeKind.FILE)):
        if not fnode.path:
            continue
        parent = posixpath.dirname(fnode.path)
        if not parent:
            continue  # top-level file: no directory boundary to represent
        _ensure_module_chain(graph, parent)
        graph.add_edge(
            Edge(
                src=module_id(parent),
                dst=fnode.id,
                kind=EdgeKind.CONTAINS,
                provenance=Provenance.FS,
                confidence=Confidence.EXACT,
            )
        )


def _ensure_module_chain(graph: KnowledgeGraph, dir_path: str) -> None:
    """Add a ``module`` node for ``dir_path`` and each ancestor, linked top-down."""
    parts = dir_path.split("/")
    for i, name in enumerate(parts):
        sub = "/".join(parts[: i + 1])
        graph.add_node(
            Node(
                id=module_id(sub),
                kind=NodeKind.MODULE,
                label=name,
                path=sub,
                provenance=Provenance.FS,
            )
        )
        if i > 0:
            graph.add_edge(
                Edge(
                    src=module_id("/".join(parts[:i])),
                    dst=module_id(sub),
                    kind=EdgeKind.CONTAINS,
                    provenance=Provenance.FS,
                    confidence=Confidence.EXACT,
                )
            )


def build_graph(root: str, **kwargs) -> KnowledgeGraph:
    """Convenience wrapper: build and return a graph for ``root``."""
    return GraphBuilder(root, **kwargs).build()
