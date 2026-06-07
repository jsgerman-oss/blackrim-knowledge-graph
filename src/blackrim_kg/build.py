"""Assemble a :class:`~blackrim_kg.graph.KnowledgeGraph` from a project corpus.

The builder orchestrates the *spine*: walk the corpus, run ast-lens per code
file, and fold each outline into the graph as file/symbol/import nodes with
``contains`` and ``imports`` edges. The enrichment layers the architecture
defines — import resolution (coarse import names -> concrete file/module
nodes), reference and call edges, documentation, and semantic concepts — attach
after the spine exists and are intentionally left as follow-up work (see
ARCHITECTURE.md §"Implementation roadmap").

The ast-lens call is injected as ``outline_fn`` so the builder is testable
without ast-lens installed and so alternative structure sources can be swapped
in. When ast-lens is unavailable, ``outline_fn`` returns ``None`` and the build
still records a filesystem-level file node per source file.
"""

from __future__ import annotations

from collections.abc import Callable

from .astlens import ParsedOutline, outline_to_graph, run_outline
from .graph import KnowledgeGraph
from .model import Node, NodeKind, Provenance, file_id
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
        return graph


def build_graph(root: str, **kwargs) -> KnowledgeGraph:
    """Convenience wrapper: build and return a graph for ``root``."""
    return GraphBuilder(root, **kwargs).build()
