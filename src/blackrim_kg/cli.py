"""The ``kg`` command line — build a graph, then query and export it.

    kg build <path> [--out DIR] [--budget N] [--threshold N] [--docs]
    kg search <text> [--graph FILE] [--kind KIND]
    kg neighbors <node-id> [--graph FILE] [--direction out|in|both]
    kg path <a> <b> [--graph FILE] [--undirected]
    kg deps <node-id> [--graph FILE] [--reverse]
    kg explain <node-id> [--graph FILE]
    kg export (json|html|report) [--graph FILE] [--out FILE]

``build`` writes ``<out>/graph.json`` (default ``kg-out/``); every other command
reads that JSON. The build stage runs ast-lens per file when it is available and
otherwise records filesystem-level file nodes — so the command always produces a
graph, just a thinner one without ast-lens. See ARCHITECTURE.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .build import GraphBuilder
from .export import dump_json, render_html, render_report
from .export.graph_json import load_json, to_json_obj
from .graph import KnowledgeGraph
from .model import NodeKind
from .query import dependencies, dependents, explain, neighbors, path, search

DEFAULT_OUT = "kg-out"
DEFAULT_GRAPH = os.path.join(DEFAULT_OUT, "graph.json")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"kg: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"kg: node not found: {exc}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"kg {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_build = sub.add_parser("build", help="build a graph from a project corpus")
    p_build.add_argument("path", help="project root to scan")
    p_build.add_argument("--out", default=DEFAULT_OUT, help=f"output dir (default: {DEFAULT_OUT})")
    p_build.add_argument("--budget", type=int, default=300, help="ast-lens token budget")
    p_build.add_argument("--threshold", type=int, default=0, help="ast-lens min-LoC threshold")
    p_build.add_argument("--docs", action="store_true", help="also record documentation files")
    p_build.set_defaults(func=_cmd_build)

    p_search = sub.add_parser("search", help="find nodes by name/id substring")
    p_search.add_argument("text")
    _add_graph_arg(p_search)
    p_search.add_argument("--kind", choices=[k.value for k in NodeKind])
    p_search.set_defaults(func=_cmd_search)

    p_neigh = sub.add_parser("neighbors", help="list a node's neighbours")
    p_neigh.add_argument("node_id")
    _add_graph_arg(p_neigh)
    p_neigh.add_argument("--direction", choices=["out", "in", "both"], default="both")
    p_neigh.set_defaults(func=_cmd_neighbors)

    p_path = sub.add_parser("path", help="shortest path between two nodes")
    p_path.add_argument("src")
    p_path.add_argument("dst")
    _add_graph_arg(p_path)
    p_path.add_argument("--undirected", action="store_true")
    p_path.set_defaults(func=_cmd_path)

    p_deps = sub.add_parser("deps", help="dependencies (or, with --reverse, dependents)")
    p_deps.add_argument("node_id")
    _add_graph_arg(p_deps)
    p_deps.add_argument("--reverse", action="store_true", help="show what depends on the node")
    p_deps.set_defaults(func=_cmd_deps)

    p_explain = sub.add_parser("explain", help="describe a node and its neighbourhood")
    p_explain.add_argument("node_id")
    _add_graph_arg(p_explain)
    p_explain.set_defaults(func=_cmd_explain)

    p_export = sub.add_parser("export", help="export the graph (json|html|report)")
    p_export.add_argument("format", choices=["json", "html", "report"])
    _add_graph_arg(p_export)
    p_export.add_argument("--out", help="output file (default: stdout)")
    p_export.set_defaults(func=_cmd_export)

    return parser


def _add_graph_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--graph", default=DEFAULT_GRAPH, help=f"graph JSON (default: {DEFAULT_GRAPH})")


def _load(args: argparse.Namespace) -> KnowledgeGraph:
    if not os.path.exists(args.graph):
        raise FileNotFoundError(f"graph not found: {args.graph} (run `kg build` first)")
    return load_json(args.graph)


def _cmd_build(args: argparse.Namespace) -> int:
    builder = GraphBuilder(
        args.path, budget=args.budget, threshold=args.threshold, include_docs=args.docs
    )
    graph = builder.build()
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "graph.json")
    dump_json(graph, out_path, root=os.path.abspath(args.path))
    stats = graph.stats()
    print(f"built {stats['node_count']} nodes, {stats['edge_count']} edges -> {out_path}")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    graph = _load(args)
    kind = NodeKind(args.kind) if args.kind else None
    hits = search(graph, args.text, kind=kind)
    for n in hits:
        print(f"{n.id}\t{n.kind.value}\t{n.label}")
    if not hits:
        print("(no matches)", file=sys.stderr)
    return 0


def _cmd_neighbors(args: argparse.Namespace) -> int:
    graph = _load(args)
    for n in neighbors(graph, args.node_id, direction=args.direction):
        print(f"{n.id}\t{n.kind.value}\t{n.label}")
    return 0


def _cmd_path(args: argparse.Namespace) -> int:
    graph = _load(args)
    result = path(graph, args.src, args.dst, directed=not args.undirected)
    if result is None:
        print("(no path)", file=sys.stderr)
        return 1
    print(" -> ".join(n.id for n in result))
    return 0


def _cmd_deps(args: argparse.Namespace) -> int:
    graph = _load(args)
    fn = dependents if args.reverse else dependencies
    for n in fn(graph, args.node_id):
        print(f"{n.id}\t{n.kind.value}\t{n.label}")
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    graph = _load(args)
    result = explain(graph, args.node_id)
    if result is None:
        print(f"kg: node not found: {args.node_id}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    graph = _load(args)
    if args.format == "json":
        text = json.dumps(to_json_obj(graph), indent=2, sort_keys=True)
    elif args.format == "html":
        text = render_html(graph)
    else:
        text = render_report(graph)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
            if not text.endswith("\n"):
                fh.write("\n")
        print(f"wrote {args.format} -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
