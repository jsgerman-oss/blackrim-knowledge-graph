# blackrim-knowledge-graph — pack

The gas-city pack that surfaces the `blackrim_kg` engine (one directory up, in
the repo's `src/`) inside a city: build a queryable, AST-first knowledge graph of
a project and ask it structural questions instead of grepping.

This mirrors the cockpit / provider-forge pack conventions: a minimal `pack.toml`
([pack] only — skills and commands are discovered by directory convention), a
`bin/` wrapper, `setup.sh` / `install.sh` / `uninstall.sh` lifecycle scripts, and
a self-contained `.venv`.

## What it provides

| Path | Role |
|------|------|
| `bin/kg` | the build / query / export CLI (wraps `python -m blackrim_kg.cli`) |
| `skills/knowledge-graph-build/` | skill: build a project's graph from its corpus |
| `skills/knowledge-graph-query/` | skill: query and export an existing graph |
| `setup.sh` | build the engine venv (installs the engine editable) |
| `install.sh` / `uninstall.sh` | reversible, idempotent town/rig install lifecycle |

The engine lives at the repository root (`../src/blackrim_kg`), not inside this
pack — see the repo `ARCHITECTURE.md`. This repository is vendored into a city
*whole* (engine + pack), so the pack is imported with
`source = "packs/blackrim-knowledge-graph/pack"`.

## Quickstart

```bash
./setup.sh                       # build .venv and install the engine into it
export AST_LENS_BIN=/path/to/packs/ast-lens/bin/outline   # optional, for symbols
./bin/kg build /path/to/project  # writes kg-out/graph.json
./bin/kg export report           # human-readable summary
./bin/kg export html --out graph.html
```

`bin/kg` also runs under a bare `python3` (no venv) because it puts the engine's
source on `PYTHONPATH`.

## Install into a city

Vendor this repository under the city (e.g. as `packs/blackrim-knowledge-graph/`),
then turn the pack on:

```bash
packs/blackrim-knowledge-graph/pack/install.sh --town
# or scope to one rig:
packs/blackrim-knowledge-graph/pack/install.sh --rig <name>
```

Reverse with `uninstall.sh` (same scope flags; `--purge` also deletes `.venv`).
Both scripts are idempotent and back up any config they edit.

## Tests

The engine's test suite lives at the repo root:

```bash
cd .. && PYTHONPATH=src python3 -m pytest -q
```

## License

MIT — see the repository [LICENSE](../LICENSE).
