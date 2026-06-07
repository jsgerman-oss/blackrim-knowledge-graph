"""CLI: argument wiring and the build -> query/export round trip.

These run hermetically: ``AST_LENS_BIN`` is pointed at a nonexistent path so the
build records filesystem-level file nodes without needing ast-lens installed.
"""

from __future__ import annotations

import json
import os

import pytest

from blackrim_kg import cli


@pytest.fixture(autouse=True)
def _no_astlens(monkeypatch):
    monkeypatch.setenv("AST_LENS_BIN", "/nonexistent/outline-binary")


def test_version_exits_zero():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0


def test_no_command_prints_help_and_returns_zero(capsys):
    assert cli.main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_build_then_query_and_export(tmp_path, capsys):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("x = 1\n")
    out = tmp_path / "out"

    assert cli.main(["build", str(project), "--out", str(out)]) == 0
    graph_path = out / "graph.json"
    assert graph_path.exists()
    data = json.loads(graph_path.read_text())
    assert data["stats"]["node_count"] >= 1
    capsys.readouterr()

    # search finds the file node
    assert cli.main(["search", "app", "--graph", str(graph_path)]) == 0
    assert "file:app.py" in capsys.readouterr().out

    # explain an existing node
    assert cli.main(["explain", "file:app.py", "--graph", str(graph_path)]) == 0
    capsys.readouterr()

    # export each format to a file
    for fmt in ("json", "report", "html"):
        dest = tmp_path / f"graph.{fmt}"
        assert cli.main(["export", fmt, "--graph", str(graph_path), "--out", str(dest)]) == 0
        assert dest.exists() and dest.stat().st_size > 0
        capsys.readouterr()


def test_query_on_missing_graph_errors(tmp_path):
    missing = tmp_path / "nope.json"
    assert cli.main(["search", "x", "--graph", str(missing)]) == 2


def test_explain_unknown_node_returns_two(tmp_path):
    # Build a tiny graph first so the graph file exists.
    project = tmp_path / "p"
    project.mkdir()
    (project / "a.py").write_text("y = 2\n")
    out = tmp_path / "o"
    cli.main(["build", str(project), "--out", str(out)])
    graph_path = out / "graph.json"
    assert cli.main(["explain", "sym:does#function:notexist", "--graph", str(graph_path)]) == 2
    assert os.path.exists(graph_path)
