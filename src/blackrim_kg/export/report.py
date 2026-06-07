"""A human-readable Markdown report over the graph.

The report is the "read it like prose" view: corpus summary, the most connected
symbols (the de-facto hubs of the codebase), a per-language file breakdown, and
the provenance/confidence mix so a reader can see how much of the graph is exact
spine versus inference. It is deterministic so it diffs cleanly.
"""

from __future__ import annotations

from ..graph import KnowledgeGraph
from ..model import EdgeKind, NodeKind
from ..query import most_connected


def render_report(graph: KnowledgeGraph, *, root: str | None = None, top_n: int = 20) -> str:
    stats = graph.stats()
    lines: list[str] = []
    lines.append("# Knowledge Graph Report")
    lines.append("")
    if root:
        lines.append(f"**Root:** `{root}`")
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Nodes: **{stats['node_count']}**")
    lines.append(f"- Edges: **{stats['edge_count']}**")
    lines.append("")

    lines.append("### Nodes by kind")
    lines.append("")
    lines.extend(_count_table(stats["nodes_by_kind"], "kind"))
    lines.append("")

    lines.append("### Edges by kind")
    lines.append("")
    lines.extend(_count_table(stats["edges_by_kind"], "relation"))
    lines.append("")

    lines.append("### Provenance & confidence")
    lines.append("")
    lines.append(f"- Node provenance: {_inline_counts(stats['node_provenance'])}")
    lines.append(f"- Edge confidence: {_inline_counts(stats['edge_confidence'])}")
    lines.append("")

    lines.append(f"## Most connected symbols (top {top_n})")
    lines.append("")
    ranked = most_connected(graph, top_n=top_n, kind=NodeKind.SYMBOL)
    if ranked:
        lines.append("| Symbol | Kind | Degree | Location |")
        lines.append("| --- | --- | ---: | --- |")
        for node, deg in ranked:
            skind = node.attrs.get("symbol_kind", "")
            loc = _location(node)
            lines.append(f"| `{node.label}` | {skind} | {deg} | {loc} |")
    else:
        lines.append("_No symbol nodes yet — run a build with ast-lens available._")
    lines.append("")

    lines.append("## Files")
    lines.append("")
    files = list(graph.nodes(NodeKind.FILE))
    by_lang: dict[str, int] = {}
    for f in files:
        by_lang[f.lang or "unknown"] = by_lang.get(f.lang or "unknown", 0) + 1
    lines.append(f"- Total files: **{len(files)}**")
    for lang, count in sorted(by_lang.items()):
        lines.append(f"  - {lang}: {count}")
    lines.append("")

    modules = list(graph.nodes(NodeKind.MODULE))
    lines.append(f"## Module boundaries ({len(modules)})")
    lines.append("")
    if modules:
        ranked = sorted(
            ((m, _direct_file_count(graph, m.id)) for m in modules),
            key=lambda pair: (-pair[1], pair[0].path or pair[0].id),
        )
        lines.append("| Module | Files |")
        lines.append("| --- | ---: |")
        for module, fcount in ranked[:top_n]:
            lines.append(f"| `{module.path or module.label}` | {fcount} |")
    else:
        lines.append("_No module nodes — a flat corpus, or the build produced no files._")
    lines.append("")

    orphans = [n for n in graph.nodes() if graph.degree(n.id) == 0]
    lines.append(f"## Orphans ({len(orphans)})")
    lines.append("")
    lines.append("_Nodes with no edges — candidates for missing resolution or dead code._")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _direct_file_count(graph: KnowledgeGraph, module_id: str) -> int:
    """How many ``file`` nodes a module directly ``contains`` (not recursive)."""
    total = 0
    for e in graph.out_edges(module_id, [EdgeKind.CONTAINS]):
        child = graph.get(e.dst)
        if child is not None and child.kind is NodeKind.FILE:
            total += 1
    return total


def _count_table(counts: dict[str, int], label: str) -> list[str]:
    if not counts:
        return ["_(none)_"]
    rows = [f"| {label} | count |", "| --- | ---: |"]
    for key, value in sorted(counts.items()):
        rows.append(f"| {key} | {value} |")
    return rows


def _inline_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "_(none)_"
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def _location(node) -> str:
    if node.path and node.span:
        return f"`{node.path}:{node.span.start_line}`"
    if node.path:
        return f"`{node.path}`"
    return ""
