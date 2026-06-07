"""GraphBuilder: corpus walk + injected outline, with skip-dir pruning."""

from __future__ import annotations

from blackrim_kg.astlens import Decl, ParsedOutline
from blackrim_kg.build import GraphBuilder, add_module_boundaries
from blackrim_kg.graph import KnowledgeGraph
from blackrim_kg.model import EdgeKind, Node, NodeKind, Provenance, Span, SymbolKind


def _fake_outline(df):
    """Return a one-symbol outline for any code file (no ast-lens needed)."""
    return ParsedOutline(
        file=df.rel_path,
        loc=42,
        decl_count=1,
        module_doc=None,
        imports=["os"],
        decls=[
            Decl(
                section="Functions",
                name="main",
                sig="def main()",
                symbol_kind=SymbolKind.FUNCTION,
                span=Span(1, 3),
            )
        ],
    )


def test_build_folds_outlines_into_spine(tmp_path):
    (tmp_path / "app.py").write_text("def main():\n    pass\n")
    (tmp_path / "util.py").write_text("def helper():\n    pass\n")
    g = GraphBuilder(str(tmp_path), outline_fn=_fake_outline).build()

    files = list(g.nodes(NodeKind.FILE))
    assert {f.path for f in files} == {"app.py", "util.py"}
    assert all(f.provenance is Provenance.AST for f in files)

    symbols = list(g.nodes(NodeKind.SYMBOL))
    assert {s.label for s in symbols} == {"main"}  # one per file, same name
    # two files each contain a `main`, deduped IDs by path keep them distinct
    assert len(symbols) == 2


def test_build_skips_vendor_and_vcs_dirs(tmp_path):
    (tmp_path / "keep.py").write_text("x = 1\n")
    vendored = tmp_path / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "skip.py").write_text("y = 2\n")
    git = tmp_path / ".git"
    git.mkdir()
    (git / "hook.py").write_text("z = 3\n")

    g = GraphBuilder(str(tmp_path), outline_fn=_fake_outline).build()
    paths = {f.path for f in g.nodes(NodeKind.FILE)}
    assert paths == {"keep.py"}


def test_build_without_outline_still_records_files(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    # outline_fn returns None -> filesystem-provenance file node, no symbols.
    g = GraphBuilder(str(tmp_path), outline_fn=lambda df: None).build()
    files = list(g.nodes(NodeKind.FILE))
    assert len(files) == 1
    assert files[0].provenance is Provenance.FS
    assert list(g.nodes(NodeKind.SYMBOL)) == []


def test_build_synthesizes_module_boundaries(tmp_path):
    pkg = tmp_path / "src" / "app"
    pkg.mkdir(parents=True)
    (pkg / "main.py").write_text("def main():\n    pass\n")
    (pkg / "util.py").write_text("def helper():\n    pass\n")
    g = GraphBuilder(str(tmp_path), outline_fn=_fake_outline).build()

    # One module node per ancestor directory, path-form ids, fs provenance.
    modules = {m.id: m for m in g.nodes(NodeKind.MODULE)}
    assert set(modules) == {"mod:src", "mod:src/app"}
    assert modules["mod:src/app"].label == "app"
    assert modules["mod:src/app"].path == "src/app"
    assert all(m.provenance is Provenance.FS for m in modules.values())

    # Hierarchy: src contains src/app; src/app contains both files (fs/exact).
    fs_contains = {
        (e.src, e.dst)
        for e in g.edges(EdgeKind.CONTAINS)
        if e.provenance is Provenance.FS
    }
    assert ("mod:src", "mod:src/app") in fs_contains
    assert ("mod:src/app", "file:src/app/main.py") in fs_contains
    assert ("mod:src/app", "file:src/app/util.py") in fs_contains

    # The ast-derived file->symbol containment stays provenance=ast, so module
    # boundaries never collide with it on the edge identity tuple.
    ast_contains = [e for e in g.edges(EdgeKind.CONTAINS) if e.provenance is Provenance.AST]
    assert ast_contains and all(e.src.startswith("file:") for e in ast_contains)


def test_add_module_boundaries_skips_top_level_and_is_idempotent():
    g = KnowledgeGraph()
    g.add_node(Node(id="file:top.py", kind=NodeKind.FILE, label="top.py", path="top.py"))
    g.add_node(Node(id="file:a/b/c.py", kind=NodeKind.FILE, label="c.py", path="a/b/c.py"))

    add_module_boundaries(g)
    add_module_boundaries(g)  # second pass must add nothing new

    # top.py has no parent directory -> no module; a/ and a/b/ do.
    assert {m.id for m in g.nodes(NodeKind.MODULE)} == {"mod:a", "mod:a/b"}
    fs_contains = [
        (e.src, e.dst)
        for e in g.edges(EdgeKind.CONTAINS)
        if e.provenance is Provenance.FS
    ]
    assert ("mod:a", "mod:a/b") in fs_contains
    assert ("mod:a/b", "file:a/b/c.py") in fs_contains
    assert len(fs_contains) == 2  # idempotent: no duplicate edges
