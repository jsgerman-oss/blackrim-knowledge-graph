---
name: knowledge-graph-build
description: Build a queryable, AST-first knowledge graph of a project with `kg build <path>`. The graph's spine comes from the ast-lens pack (files, symbols, containment, imports) and is written to kg-out/graph.json — a portable artifact you keep and query instead of re-grepping. Use when you want to map a codebase's structure, prepare a graph for the knowledge-graph-query skill, or refresh the graph after significant changes. Pairs with ast-lens: install/point at its `outline` binary first for symbol-level detail.
---

# Knowledge Graph: Build

## Overview

`blackrim-knowledge-graph` turns a project into a typed, directed graph — nodes
for files, symbols, imports (and, as enrichment layers land, docs and concepts);
edges for `contains`, `imports`, and (later) `calls` / `references`. The graph is
an artifact you keep (`kg-out/graph.json`) and query, rather than re-deriving
with grep on every question.

The structural **spine is AST-first**: it is sourced from the sibling
[`ast-lens`](../../../ast-lens) pack, which emits a precise per-file outline
(declarations with kind, line span, and visibility). Everything the graph asserts
as exact carries `provenance=ast`; inferred enrichment is tagged separately, so
the precise spine is never confused with heuristics.

## When to Use

- You want a **map of a codebase's structure** — which files hold which symbols,
  what imports what — as a queryable object.
- You are about to use the **`knowledge-graph-query`** skill and need a graph to
  query first.
- A project changed materially and you want to **refresh** its graph.

**When NOT to use:**

- For a one-off "where is this string" — that is plain grep. The graph earns its
  keep when you ask *structural* questions repeatedly.
- To get cross-file call/reference edges today — the scaffold's spine is files,
  symbols, containment, and imports; richer edges are a defined follow-up
  (see ARCHITECTURE.md §"Implementation roadmap").

## Process

### Step 1 — Make ast-lens available (recommended)

The spine is richest when ast-lens can emit symbol outlines. Ensure its
`outline` binary is reachable, either on `PATH` or via `$AST_LENS_BIN`:

```bash
export AST_LENS_BIN=/path/to/packs/ast-lens/bin/outline
```

Without it, `kg build` still runs — it records a filesystem-level node per source
file (no symbols). With it, you get files **and** symbols, containment, and imports.

### Step 2 — Build the graph

```bash
kg build .                      # scan the current project; write kg-out/graph.json
kg build /path/to/project       # scan an explicit root
kg build . --docs               # also record documentation files
kg build . --budget 500         # raise the ast-lens per-file token budget
```

`build` walks the corpus (skipping VCS, vendor, build, and virtual-env
directories), runs ast-lens per code file, folds each outline into the graph, and
writes a deterministic `kg-out/graph.json`. It prints the node and edge counts.

### Step 3 — Sanity-check the result

```bash
kg export report                # a Markdown summary to stdout
kg search <name>                # confirm an expected symbol is present
```

## Why This Matters

- **Precise, not heuristic.** The spine is exact AST structure, so "what's in this
  file" and "what does it import" are answered from parsed truth, not pattern
  matching.
- **Portable and diff-friendly.** `graph.json` is deterministic (sorted nodes and
  edges), so you can commit it and review changes to a codebase's structure over
  time.
- **Composable.** The graph is the substrate the `knowledge-graph-query` skill (and
  downstream tools) read; building it once amortizes every later question.

## Verification Gate

Before treating a graph as ready to query:

- [ ] `kg build <path>` exited 0 and printed a non-zero node count.
- [ ] `kg-out/graph.json` exists and `kg export report` shows the expected files.
- [ ] If you expected symbols, ast-lens was reachable (the report's node counts
      include `symbol` nodes, not only `file` nodes).

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack contributes a
skill by placing `skills/<name>/SKILL.md` under the pack root, with YAML frontmatter
carrying at minimum `name` and `description`. This file lives at
`pack/skills/knowledge-graph-build/SKILL.md`, so it is picked up automatically —
`pack.toml` does not enumerate skills. Once the `blackrim-knowledge-graph` pack is
imported into a city (vendored and registered via a direct
`source = "packs/blackrim-knowledge-graph/pack"` import), the skill surfaces in
`gc skill list` binding-qualified as `blackrim-knowledge-graph.knowledge-graph-build`.
Verify with `gc skill list` (and `gc lint .` / `gc doctor`).
