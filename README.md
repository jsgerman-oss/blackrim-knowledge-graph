# blackrim-knowledge-graph

Map a project (code, docs, and structured artifacts) into a queryable knowledge graph, so an AI coding assistant, or a human, can ask the codebase questions instead of grepping through it file by file.

blackrim-knowledge-graph is a clean-room, MIT-licensed pack in the blackrim toolchain. It is built to compose with the ast-lens pack as a first-class graph source: precise, AST-derived structure (symbols, references, call edges, module boundaries) becomes the spine of the graph, enriched with docs and other artifacts.

> Status: early scaffolding. This repository is the home of the design and the implementation as it lands.

## Why

Grep and a file tree answer "where is this string"; they do not answer "what depends on this", "how does a request flow from the route to the store", or "which concepts are central, and how do they connect". A knowledge graph makes the structure of a project a first-class, queryable object: nodes for concepts, symbols, files, and artifacts, and edges for the relationships between them.

## Design goals

- Original and clean-room. Inspired by the knowledge-graph idea, built as our own.
- AST-first. ast-lens supplies exact structure, so the graph is precise rather than heuristic.
- Queryable and portable. The graph is an artifact you keep and query, not a one-shot read.
- Composable with gas town. Surfaced as a pack, so a gas city's agents can build and query a project graph.
- MIT, and honest about its sources.

## Layout

To be built out: the graph engine, the pack, an interactive viewer, and the export formats.

## License

MIT. Copyright (c) 2026 Blackrim.dev. See [LICENSE](LICENSE).
