# blackrim-knowledge-graph

Map a project (code, docs, and structured artifacts) into a queryable knowledge graph, so an AI coding assistant, or a human, can ask the codebase questions instead of grepping through it file by file.

blackrim-knowledge-graph is a MIT-licensed pack in the blackrim toolchain. It is built to compose with the ast-lens pack as a first-class graph source: precise, AST-derived structure (symbols, references, call edges, module boundaries) becomes the spine of the graph, enriched with docs and other artifacts.

> Status: early scaffolding. This repository is the home of the design and the implementation as it lands.

## Why

Grep and a file tree answer "where is this string"; they do not answer "what depends on this", "how does a request flow from the route to the store", or "which concepts are central, and how do they connect". A knowledge graph makes the structure of a project a first-class, queryable object: nodes for concepts, symbols, files, and artifacts, and edges for the relationships between them.

## Design goals

- AST-first. ast-lens supplies exact structure, so the graph is precise rather than heuristic.
- Queryable and portable. The graph is an artifact you keep and query, not a one-shot read.
- Composable with gas town. Surfaced as a pack, so a gas city's agents can build and query a project graph.
- MIT, and honest about its sources.

## Layout

The full design is in [ARCHITECTURE.md](ARCHITECTURE.md). The repository is scaffolded as:

- `src/blackrim_kg/` — the engine: the graph model (`model.py`), the in-memory graph (`graph.py`), the ast-lens adapter (`astlens.py`), the corpus walker (`sources.py`), the builder (`build.py`), queries (`query.py`), the exporters (`export/`: JSON, HTML, Markdown report), and the `kg` CLI (`cli.py`).
- `pack/` — the gas-city pack (mirrors the cockpit conventions): `bin/kg`, the `knowledge-graph-build` / `knowledge-graph-query` skills, and the `setup.sh` / `install.sh` / `uninstall.sh` lifecycle.
- `tests/` — the pytest suite.

What's implemented today is the precise **spine** (files, symbols, containment, imports) and the query/export surface; the enrichment layers (cross-file reference/call edges, documentation, semantic concepts, the interactive renderer) are defined as follow-up work in [ARCHITECTURE.md §11](ARCHITECTURE.md).

### Quickstart

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e .
export AST_LENS_BIN=/path/to/packs/ast-lens/bin/outline   # optional, for symbol-level detail
kg build .            # writes kg-out/graph.json
kg export report      # human-readable summary
kg search <name>      # find nodes; then `kg explain <id>`, `kg deps <id>`
```

## License

MIT. Copyright (c) 2026 Blackrim.dev. See [LICENSE](LICENSE).
