"""A single self-contained interactive HTML view of the graph.

Design choices (original to this project — see ARCHITECTURE.md §"Exports"):

- **One file, no network.** The graph is embedded inline as JSON; the page works
  offline and can be committed or emailed as a single artifact.
- **Progressive.** The scaffold ships a server-rendered, readable view (counts,
  nodes grouped by kind, a live text filter) plus the embedded data and a small
  enhancer hook. The full force-directed canvas renderer is a defined follow-up
  that reads the same embedded ``#kg-graph`` payload, so the data contract is
  stable now even though the visualization deepens later.

The renderer here is intentionally dependency-free and small; it is *not* a port
of any existing viewer.
"""

from __future__ import annotations

import html as _html
import json

from ..graph import KnowledgeGraph
from ..model import NodeKind
from .graph_json import to_json_obj

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 14px/1.5 system-ui, sans-serif; margin: 0; padding: 1.5rem; }
  h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
  .meta { color: #888; margin-bottom: 1rem; }
  .stats { display: flex; flex-wrap: wrap; gap: .5rem 1rem; margin-bottom: 1rem; }
  .stats span { background: rgba(127,127,127,.15); border-radius: 4px; padding: .15rem .5rem; }
  #filter { width: 100%; max-width: 28rem; padding: .4rem .6rem; margin-bottom: 1rem;
            border: 1px solid rgba(127,127,127,.4); border-radius: 6px; }
  .group { margin-bottom: 1.25rem; }
  .group h2 { font-size: 1rem; border-bottom: 1px solid rgba(127,127,127,.3); padding-bottom: .2rem; }
  ul { list-style: none; padding-left: 0; margin: .4rem 0; }
  li { padding: .1rem 0; }
  .id { color: #888; font-size: .85em; }
  code { background: rgba(127,127,127,.15); border-radius: 3px; padding: 0 .25rem; }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<div class="meta">__META__</div>
<div class="stats">__STATS__</div>
<input id="filter" type="search" placeholder="Filter nodes by name or id…" autocomplete="off">
<div id="graph-view">__BODY__</div>

<script type="application/json" id="kg-graph">__DATA__</script>
<script>
// Minimal enhancer: live client-side filtering over the server-rendered list.
// The full force-directed renderer (a follow-up) reads the same #kg-graph JSON.
(function () {
  var input = document.getElementById("filter");
  if (!input) return;
  var items = Array.prototype.slice.call(document.querySelectorAll("li[data-key]"));
  input.addEventListener("input", function () {
    var q = input.value.toLowerCase();
    items.forEach(function (li) {
      li.style.display = li.getAttribute("data-key").indexOf(q) === -1 ? "none" : "";
    });
    document.querySelectorAll(".group").forEach(function (g) {
      var any = Array.prototype.some.call(g.querySelectorAll("li[data-key]"), function (li) {
        return li.style.display !== "none";
      });
      g.style.display = any ? "" : "none";
    });
  });
})();
</script>
</body>
</html>
"""


def render_html(graph: KnowledgeGraph, *, title: str = "Knowledge Graph", root: str | None = None) -> str:
    payload = to_json_obj(graph, root=root)
    stats = payload["stats"]
    # Escape "</" so an embedded string can never close the <script> early.
    data = json.dumps(payload, sort_keys=True).replace("</", "<\\/")

    meta = f"{stats['node_count']} nodes · {stats['edge_count']} edges"
    if root:
        meta += f" · root <code>{_html.escape(root)}</code>"

    stat_spans = "".join(
        f"<span>{_html.escape(k)}: {v}</span>"
        for k, v in sorted(stats["nodes_by_kind"].items())
    )

    body = _render_body(graph)

    return (
        _TEMPLATE.replace("__TITLE__", _html.escape(title))
        .replace("__META__", meta)
        .replace("__STATS__", stat_spans or "<span>empty graph</span>")
        .replace("__BODY__", body)
        .replace("__DATA__", data)
    )


def _render_body(graph: KnowledgeGraph) -> str:
    parts: list[str] = []
    for kind in NodeKind:
        nodes = list(graph.nodes(kind))
        if not nodes:
            continue
        parts.append('<div class="group">')
        parts.append(f"<h2>{_html.escape(kind.value)} ({len(nodes)})</h2>")
        parts.append("<ul>")
        for n in nodes:
            key = f"{n.label} {n.id}".lower()
            deg = graph.degree(n.id)
            loc = ""
            if n.path:
                loc = f" <span class=\"id\">{_html.escape(n.path)}</span>"
            parts.append(
                f'<li data-key="{_html.escape(key)}">'
                f"<code>{_html.escape(n.label)}</code> "
                f'<span class="id">[deg {deg}]</span>{loc}</li>'
            )
        parts.append("</ul></div>")
    return "\n".join(parts) or "<p>Empty graph.</p>"
