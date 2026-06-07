---
name: knowledge-graph-query
description: Query and export an already-built project knowledge graph. Use `kg search` to find nodes, `kg neighbors` / `kg explain` to inspect a node's connections, `kg deps` (and `--reverse`) for forward/backward dependencies, `kg path` for how two nodes connect, and `kg export json|html|report` for portable views. Use when answering structural questions about a codebase ("what depends on X", "how does A reach B", "what are the hub symbols") from the graph that knowledge-graph-build produced. Run knowledge-graph-build first.
---

# Knowledge Graph: Query

## Overview

Once `knowledge-graph-build` has written `kg-out/graph.json`, this skill answers
structural questions against it — cheaply, deterministically, and without an LLM
in the loop. The graph is directed and typed, so questions have precise meanings:
"dependencies" follow `imports` / `calls` / `references` edges forward;
"dependents" follow them backward.

## When to Use

- "**What depends on** this symbol/file?" → `kg deps --reverse`.
- "**What does** this depend on?" → `kg deps`.
- "**How do** these two things connect?" → `kg path`.
- "**What are the hubs** of this codebase?" → `kg export report` (most-connected
  symbols), or `kg neighbors` to walk out from one.
- You need a **portable view** to share or commit → `kg export json|html|report`.

**When NOT to use:**

- Before a graph exists — run `knowledge-graph-build` first. Query commands exit
  non-zero with a clear message if `kg-out/graph.json` is missing.

## Process

### Step 1 — Find the node you care about

Node IDs are stable and human-readable (`file:<path>`, `sym:<path>#<kind>:<name>`,
`imp:<path>-><module>`). Find one by substring:

```bash
kg search Session                 # any node whose name/id contains "Session"
kg search . --kind file           # list file nodes
```

### Step 2 — Inspect and traverse

```bash
kg explain "sym:store.go#type:Session"     # node + grouped in/out neighbours (JSON)
kg neighbors "file:store.go"               # adjacent nodes
kg deps "sym:store.go#function:New"        # what New depends on
kg deps "sym:store.go#type:Session" --reverse   # what depends on Session
kg path "file:api.go" "sym:store.go#type:Session"   # shortest connecting path
```

Pass `--graph <file>` if your graph is not at the default `kg-out/graph.json`.

### Step 3 — Export a portable view

```bash
kg export report                 # Markdown summary (counts, hubs, provenance mix)
kg export html --out graph.html  # single self-contained, offline HTML view
kg export json                   # the canonical node-link JSON (to stdout)
```

## Why This Matters

- **Precise questions, precise answers.** Dependency direction is a property of the
  edge type, so `deps` vs `deps --reverse` mean exactly forward vs backward over
  dependency edges — not a fuzzy neighbourhood.
- **Confidence is visible.** Every edge carries a confidence (`exact` / `resolved`
  / `inferred`); the report breaks this down so you know how much of an answer
  rests on the exact spine versus inference.
- **No recompute.** Queries read the stored graph; you pay the build cost once.

## Verification Gate

Before trusting a query's answer:

- [ ] `kg-out/graph.json` exists (or you passed the right `--graph`).
- [ ] The node IDs you queried exist (`kg search` first if unsure — a typo'd ID
      yields an empty result or a "node not found" exit, not a wrong answer).
- [ ] For dependency questions, you used the direction you meant (`deps` =
      forward, `deps --reverse` = who depends on it).

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack contributes a
skill by placing `skills/<name>/SKILL.md` under the pack root, with YAML frontmatter
carrying at minimum `name` and `description`. This file lives at
`pack/skills/knowledge-graph-query/SKILL.md`, so it is picked up automatically —
`pack.toml` does not enumerate skills. Once the `blackrim-knowledge-graph` pack is
imported into a city (vendored and registered via a direct
`source = "packs/blackrim-knowledge-graph/pack"` import), the skill surfaces in
`gc skill list` binding-qualified as `blackrim-knowledge-graph.knowledge-graph-query`.
Verify with `gc skill list` (and `gc lint .` / `gc doctor`).
