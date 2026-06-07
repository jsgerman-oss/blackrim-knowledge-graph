# blackrim-knowledge-graph — Architecture

> Status: **scaffold**. This document is the design of record. The repository
> ships the *spine* of the engine (model, graph container, ast-lens adapter,
> query, exporters, CLI) plus the gas-city pack skeleton; the enrichment layers
> the design defines are tracked as follow-up work in §11.
>
> Original and clean-room — see §10. MIT, Copyright (c) 2026 Blackrim.dev.

## 1. What this is

`blackrim-knowledge-graph` maps a project — code first, documentation and other
structured artifacts next — into a typed, directed graph you keep and query,
instead of re-deriving structure with grep on every question. Grep answers
"where is this string"; the graph answers "what depends on this", "how does a
request flow from the route to the store", and "which symbols are central, and
how do they connect".

Its defining choice: the structural **spine is AST-first and precise**, sourced
from the sibling [`ast-lens`](https://example.invalid/ast-lens) pack rather than
from heuristics. Everything the graph asserts as exact is provenance-tagged as
such, and the inferred/enriched layers sit cleanly on top — never blended into
the spine.

## 2. Goals and non-goals

**Goals**

- **Precise, not heuristic.** The spine (files, symbols, containment, imports) is
  exact AST structure. A query over the spine is answered from parsed truth.
- **Queryable and portable.** The graph is an artifact (`kg-out/graph.json`) you
  keep, commit, diff, and query — not a one-shot read.
- **Composable with gas town.** Surfaced as a pack so a city's agents can build
  and query a project graph (§9).
- **Separable layers.** Provenance and confidence are first-class, so a consumer
  can always reduce the graph to "only what is exactly true".

**Non-goals (for now)**

- Not a language server. We consume ast-lens (and, later, optional supplemental
  passes) rather than reimplementing type inference.
- Not an LLM-in-the-loop tool at the spine. Semantic/concept enrichment is an
  *optional* layer, explicitly tagged `inferred` (§7.4), never required.
- Not a database. The graph is a file you keep; scaling to a server-backed store
  is a possible future, not a current concern.

## 3. Stack and rationale

**Chosen: Python 3.11+, packaged with `pyproject.toml` (PEP 621), `uv` as the
recommended toolchain, `ruff` for lint. The engine spine is pure standard
library; heavy capabilities are optional extras.**

Why Python:

1. **ast-lens is Python + tree-sitter.** Our primary structural source is a
   Python pack with a CLI (`outline`) and an in-process emitter. Consuming it —
   by subprocess today, in-process later — is most natural from Python, and any
   supplemental tree-sitter pass (§7.3) reuses the same ecosystem.
2. **The pack convention is Python.** The gas-city packs we mirror (cockpit,
   provider-forge) are a `bin/<cmd>` bash wrapper over `python -m <pkg>.cli` with
   a self-contained `.venv`. Mirroring those conventions means Python (§9).
3. **The prior art is Python/uv,** and the graph/AST ecosystem (networkx,
   tree-sitter wheels, community-detection libraries) is most mature there.

Why `uv`: fast, reproducible, lockfile-capable, and aligned with the prior art.
But nothing at runtime *requires* uv — `pyproject.toml` is standard PEP 621, so a
plain `python -m venv` + `pip install -e .` works identically. The pack's
`setup.sh` uses pip directly for exactly this reason.

Why a stdlib-only spine: the engine's core (model, graph container, query,
exporters, the ast-lens markdown adapter) imports nothing outside the standard
library, so `bin/kg` runs under any `python3` — matching the minimal footprint of
the sibling packs. Capabilities that genuinely need third-party code are
**optional extras** in `pyproject.toml`:

| Extra | Pulls in | Powers |
|-------|----------|--------|
| `algorithms` | `networkx` | weighted centrality, community detection at scale (§8) |
| `ast` | `tree-sitter*` | supplemental in-process reference/call edges (§7.3) |
| `dev` | `pytest`, `ruff` | the test + lint pipeline |

This keeps the common path dependency-free while leaving a clear seam for the
heavier layers.

## 4. Repository layout

```
blackrim-knowledge-graph/
├── ARCHITECTURE.md              # this document (design of record)
├── README.md                    # project overview
├── LICENSE                      # MIT
├── pyproject.toml               # engine metadata, extras, ruff + pytest config
├── src/blackrim_kg/             # THE ENGINE (importable package)
│   ├── __init__.py              # SCHEMA, __version__, public surface
│   ├── model.py                 # node/edge taxonomy + stable-ID helpers  (§5)
│   ├── graph.py                 # in-memory KnowledgeGraph container
│   ├── astlens.py               # ast-lens adapter: run outline + parse + map (§6)
│   ├── sources.py               # corpus discovery (filesystem walker)     (§7.1)
│   ├── build.py                 # GraphBuilder: corpus -> graph             (§7)
│   ├── query.py                 # search / neighbours / path / deps / explain (§8)
│   ├── export/                  # exporters                                  (§9-exports)
│   │   ├── graph_json.py         #   canonical node-link JSON (source of truth)
│   │   ├── report.py             #   Markdown report
│   │   └── html.py               #   single self-contained interactive HTML
│   └── cli.py                   # the `kg` command
├── pack/                        # THE GAS-CITY PACK (mirrors cockpit)        (§9-pack)
│   ├── pack.toml                #   [pack] manifest (schema = 2)
│   ├── bin/kg                   #   bash wrapper -> python -m blackrim_kg.cli
│   ├── skills/                  #   knowledge-graph-build, knowledge-graph-query
│   ├── setup.sh                 #   build the engine venv
│   ├── install.sh / uninstall.sh#   reversible town/rig install lifecycle
│   ├── requirements.txt / README.md / .gitignore
└── tests/                       # pytest suite (model, graph, adapter, build,
                                 #   query, export, cli)
```

The **engine** and the **pack** are distinct deliverables. The engine is the
source of truth; the pack is a thin city-side wrapper that installs the engine
into its `.venv` and exposes the `kg` command and the two skills. Because the
engine sits outside `pack/`, this repository is vendored into a city *whole*, and
the pack is imported as `source = "packs/blackrim-knowledge-graph/pack"` (§9-pack).

## 5. The graph model

The model lives in `model.py`. Two ideas distinguish it from a single-tier,
heuristic graph.

### 5.1 A precise spine, separable enrichment

Every node and edge records **how it was derived** and **how much to trust it**:

- `Provenance` — `ast` (exact, from ast-lens or a tree-sitter pass), `fs`
  (filesystem structure), `doc` (parsed from documentation), `inferred`
  (heuristic or model-derived).
- `Confidence` (edges) — `exact` (literally present in parsed source), `resolved`
  (produced by deterministic cross-file resolution), `inferred` (heuristic or
  probabilistic).

The spine is `provenance=ast` / `confidence=exact`. A consumer can filter the
graph down to "only what is exactly true" — or admit `resolved` and `inferred`
layers deliberately — without the two being conflated. This is the architectural
line the rest of the design holds.

### 5.2 Node taxonomy (`NodeKind`)

| Kind | Meaning | Typical provenance |
|------|---------|--------------------|
| `module` | a package / directory / logical module boundary | `fs` |
| `file` | a single source or artifact file | `ast` / `fs` |
| `symbol` | a declaration; specific kind in `attrs["symbol_kind"]` | `ast` |
| `import` | an imported module reference | `ast` |
| `doc` | a documentation file or section | `doc` |
| `concept` | a semantic/domain concept (enrichment only) | `inferred` |

A `symbol` node's `attrs["symbol_kind"]` is one of `SymbolKind`: `function`,
`method`, `class`, `type`, `interface`, `enum`, `constant`, `variable`, `other`.
Nodes also carry `label`, optional `path`, `lang`, `span` (1-based inclusive line
range), and a free `attrs` map (e.g. a symbol's `signature` and `private` flag, a
file's `loc`) — so the core schema stays small while remaining extensible.

### 5.3 Edge taxonomy (`EdgeKind`)

Edges are **directed** (`src` → `dst`) and typed:

| Kind | `src` → `dst` | Layer |
|------|---------------|-------|
| `contains` | file/module/class → child declaration | spine |
| `imports` | file/module → imported module | spine |
| `calls` | symbol → called symbol | resolution (§7.3) |
| `references` | symbol → referenced symbol (type use, etc.) | resolution |
| `inherits` | type → base type | resolution |
| `implements` | type → interface | resolution |
| `documents` | doc → documented symbol/file | docs (§7.4) |
| `mentions` | doc/concept → mentioned symbol/concept | docs / semantic |
| `relates_to` | inferred semantic relationship | semantic |

Edges carry `provenance`, `confidence`, an optional numeric `weight`, and an
`attrs` map. They are deduped by the identity tuple `(src, dst, kind,
provenance)` so re-runs and overlapping sources never inflate degree.

### 5.4 Stable, human-readable IDs

IDs use a short `scheme:body` form, built from **durable facts** so a graph diff
across edits stays small:

- file → `file:<repo-relative-path>`
- symbol → `sym:<path>#<symbol_kind>:<name>`
- import → `imp:<path>-><module>`
- module → `mod:<dotted-or-path>`
- doc → `doc:<path>[#anchor]`

Paths are normalized to forward slashes for cross-OS portability. Line spans are
**not** part of the primary key — they are carried as attributes and used only as
a last-resort disambiguator (`…@<start>-<end>`) when a file genuinely declares two
same-kind, same-name symbols. Keeping positions out of the key is what makes the
graph stable as code moves around within a file.

## 6. How ast-lens feeds the graph

ast-lens is the precise structural source. The adapter is `astlens.py`.

### 6.1 What ast-lens emits, and the contract we parse

ast-lens emits, per file, a deterministic **Markdown outline** (its "App C"
schema): the module doc, the imported module names, and declarations grouped
under `## Types` / `## Functions` / `## Values`, each with a visibility marker and
a `(L<start>–<end>)` line span. Its `--format json` envelope structures only
`file` / `lang` / `loc` / `tokens_outline` and carries the outline itself as a
`markdown` string — the structured declaration objects are internal to ast-lens.

So the **stable, version-pinned contract we depend on is the outline Markdown
schema, not a private API.** `parse_outline_markdown()` turns that schema into
structured `Decl`s (kind, name, signature, span, visibility, nested constructs);
it is pure and total (malformed input degrades, never raises) and fully tested
without ast-lens installed. `run_outline()` is the only part that shells out (to
the `outline` CLI, located via `$AST_LENS_BIN` or `PATH`), and it returns `None` —
never raises — when ast-lens is absent or passes a file through.

> **Validated against the real binary.** Run against ast-lens's own `outline`,
> the adapter parses this engine's `astlens.py` into a file node, its imports,
> and its declarations — confirming the schema contract end-to-end.

### 6.2 What maps to what

`outline_to_graph()` folds one parsed outline into the graph as the exact spine:

| ast-lens outline element | Graph contribution | Provenance |
|--------------------------|--------------------|------------|
| the file | `file` node (`label`, `lang`, `loc`, `module_doc`) | `ast` |
| a `## Types/Functions/Values` declaration | `symbol` node (kind, signature, span, `private`) | `ast` |
| file holds a declaration | `contains` edge (file → symbol) | `ast` |
| an `## Imports` entry | `import` node + `imports` edge (file → import) | `ast` |

### 6.3 What ast-lens does *not* give — and the layering that follows

ast-lens is a **structure** emitter: it says which symbols exist, where, of what
kind, and whether they are private. It does **not** emit cross-file references,
call edges, or inheritance. The architecture therefore layers explicitly:

- **Layer 0 — spine (ast-lens).** Files, symbols, containment, imports. Exact,
  deterministic. *Implemented.*
- **Layer 1 — import resolution.** Map coarse import names (ast-lens extracts the
  base module name only) to concrete `file`/`module` nodes in the corpus.
  `confidence=resolved`. *Follow-up (§11).*
- **Layer 2 — reference/call edges.** `calls` / `references` / `inherits` /
  `implements`, via a supplemental in-process tree-sitter pass (the `ast` extra)
  or an LSP-backed resolver. `confidence=resolved` (or `inferred` for a name-match
  fallback). *Follow-up.*
- **Layer 3 — artifacts & semantic.** Documentation ingestion (`doc` nodes,
  `documents`/`mentions` edges) and optional LLM concept extraction (`concept`
  nodes, `relates_to`). `provenance=doc` / `inferred`. *Follow-up.*

> **A proposed ast-lens enhancement.** Because the outline Markdown gives a clean
> machine *name* only for `## Values`, the adapter derives type/function names
> heuristically from the signature (Go receiver methods, the identifier before a
> parameter list, else the first non-keyword token). An ast-lens `--format json`
> that also emitted a structured `decls` array (name, kind, span, visibility)
> would make this exact and eliminate the heuristic. Filed as a follow-up to
> propose upstream (§11).

## 7. Build pipeline

`GraphBuilder` (`build.py`) assembles the spine.

1. **Discover (`sources.py`).** `FilesystemWalker` walks the root, classifying
   files by extension into code (aligned with ast-lens's supported languages) and,
   optionally, documentation. It prunes VCS, vendor, build, and virtual-env
   directories so a build never wanders into `node_modules` or `.git`.
2. **Spine.** For each code file, run ast-lens (injected as `outline_fn`, so the
   builder is testable without ast-lens and alternative structure sources can be
   swapped in) and fold the outline into the graph. When ast-lens is unavailable
   or passes a file through, a filesystem-provenance `file` node is still recorded
   — so a build always produces a graph, just a thinner one.
3. **Resolution / enrichment (Layers 1–3).** Defined in §6.3; attach after the
   spine exists. Left as follow-up work (§11).

## 8. Query surface

`query.py`, exposed through the `kg` CLI. Questions have precise meanings because
edges are directed and typed:

| Question | API / command |
|----------|---------------|
| find nodes by name/id | `search()` · `kg search <text> [--kind K]` |
| a node's neighbours | `neighbors()` · `kg neighbors <id> [--direction out\|in\|both]` |
| how two nodes connect | `path()` · `kg path <a> <b> [--undirected]` |
| what a node depends on | `dependencies()` · `kg deps <id>` |
| what depends on a node | `dependents()` · `kg deps <id> --reverse` |
| describe a node + neighbourhood | `explain()` · `kg explain <id>` |
| the hub symbols | `most_connected()` (degree centrality) · surfaced in the report |

"Dependencies" follow `imports`/`calls`/`references`/`inherits`/`implements`
forward; "dependents" follow them backward. Ranked, weighted, and
community-aware queries belong to the analysis layer and the `algorithms` extra.

## 9. The two surfaces: exports and the pack

### Exports

JSON is the canonical artifact; HTML and the report are derived views over the
same graph.

- **`graph_json.py` — node-link JSON (source of truth).** Deterministic (nodes
  and edges sorted, keys sorted), so `kg-out/graph.json` commits and diffs
  cleanly. Schema: `{schema, schema_version, root, stats, nodes[], edges[]}`.
  Round-trips losslessly through `KnowledgeGraph.from_dict`. Everything else reads
  this.
- **`report.py` — Markdown report.** Corpus summary, counts by node/edge kind, the
  most-connected symbols (the de-facto hubs), a per-language file breakdown, the
  provenance/confidence mix, and orphan count. Deterministic.
- **`html.py` — single self-contained interactive HTML.** The graph is embedded
  inline as JSON (with `</` neutralised so data can never close the script early),
  so the page works offline and can be committed or emailed as one file. The
  scaffold ships a server-rendered, readable view (counts, nodes grouped by kind,
  a live text filter) plus the embedded data and an enhancer hook; the full
  force-directed canvas renderer is a defined follow-up that reads the *same*
  embedded payload, so the data contract is stable now. The template is original
  to this project.

### The gas-city pack shape (mirroring cockpit)

`pack/` mirrors the cockpit / provider-forge conventions:

- **`pack.toml`** — a minimal `[pack]` manifest: `name = "blackrim-knowledge-graph"`,
  `schema = 2`, `version`. Skills and commands are **discovered by directory
  convention**, never enumerated in the manifest.
- **`bin/kg`** — a bash wrapper that resolves the pack's `.venv` python (falling
  back to system `python3`), puts the engine source on `PYTHONPATH`, and execs
  `python -m blackrim_kg.cli`. Mirrors `cockpit/bin/cockpit`.
- **`skills/<name>/SKILL.md`** — YAML frontmatter (`name`, `description`) + body.
  Two skills: `knowledge-graph-build` and `knowledge-graph-query`. They surface as
  `blackrim-knowledge-graph.<name>` once the pack is imported.
- **`setup.sh`** — builds the `.venv` and installs the engine editable into it.
- **`install.sh` / `uninstall.sh`** — reversible, idempotent town/rig install
  using the gastown direct-import pattern (a backed-up edit to `pack.toml` /
  `city.toml`, then `gc reload`, then verify). Adapted from cockpit, with a
  walk-up city detector because the pack nests under the vendored repo.

Because the engine lives at the repo root (not inside `pack/`), the repository is
vendored whole and the pack is imported with
`source = "packs/blackrim-knowledge-graph/pack"`. Publishing the engine to an
index and pinning it in `requirements.txt` instead is a packaging alternative
noted in §11.

## 10. Clean-room statement

This project was built clean-room. The prior-art knowledge-graph tool was studied
for *understanding only* — its concepts (a typed code graph, degree-based hubs,
community structure, multiple export formats, deterministic output) informed this
design, but **no code or text was copied**. The taxonomy, the provenance/confidence
model, the ID scheme, the ast-lens markdown-contract integration, the module
factoring, and the HTML template are original to this repository. Where a name is
a plain technical fact (a dependency name, tree-sitter, networkx), it is used as
such. MIT licensed, Copyright (c) 2026 Blackrim.dev.

## 11. Implementation roadmap (follow-up beads this design defines)

The scaffold implements the spine and the contracts; these layers are the defined
next steps. Each is independently shippable against the model in §5.

1. **Layer 1 — import resolution.** Resolve `import` nodes (base module names) to
   concrete `file`/`module` nodes in the corpus; add resolved `imports` edges
   between files. `confidence=resolved`. Per-language module-resolution rules.
2. **Layer 2 — reference & call edges.** A supplemental in-process tree-sitter
   pass (the `ast` extra) producing `calls` / `references` / `inherits` /
   `implements` edges, scoped per language, `confidence=resolved` (name-match
   fallback `inferred`).
3. **Propose ast-lens structured `decls` JSON.** Upstream enhancement so the
   adapter gets exact symbol names/kinds instead of the signature heuristic
   (§6.3); then switch the adapter to consume it when present.
4. **Layer 3a — documentation source.** Ingest Markdown/RST as `doc` nodes;
   `documents`/`mentions` edges to symbols and files. `provenance=doc`.
5. **Layer 3b — optional semantic enrichment.** A provider-pluggable pass adding
   `concept` nodes and `relates_to` edges, strictly `provenance=inferred` and off
   by default.
6. **Analysis layer (`algorithms` extra).** networkx-backed weighted centrality,
   community detection, and import-cycle reporting feeding a richer report.
7. **Interactive HTML renderer.** The force-directed client renderer over the
   embedded `#kg-graph` payload (filter by kind/provenance/confidence,
   click-to-inspect, search).
8. **Incremental build + caching.** Re-outline only changed files (by content
   hash) and merge into an existing graph; a `kg update` command.
9. **Packaging alternative.** Publish the engine to an index and pin it in the
   pack's `requirements.txt` so `pack/` can be vendored standalone (without the
   whole repo).
