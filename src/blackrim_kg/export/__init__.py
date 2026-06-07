"""Export surface: turn a graph into the three portable artifacts.

- :mod:`~blackrim_kg.export.graph_json` — the canonical, deterministic node-link
  JSON. This is the source of truth other tools (and the other exporters)
  consume.
- :mod:`~blackrim_kg.export.report` — a human-readable Markdown report.
- :mod:`~blackrim_kg.export.html` — a single self-contained interactive HTML view.

JSON is primary; HTML and the report are derived views over the same graph.
"""

from __future__ import annotations

from .graph_json import dump_json, to_json_obj
from .html import render_html
from .report import render_report

__all__ = ["to_json_obj", "dump_json", "render_report", "render_html"]
