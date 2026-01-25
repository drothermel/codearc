# history-extractor

Mine a Python repo's git history to extract all distinct versions of every function and class into a DuckDB database.

## Current Functionality

**Phase 1 (Core Infrastructure)** is complete:

- **Configuration models** - `ExtractionConfig` for mining settings, `IgnorePatterns` for filtering files (venv, pycache, etc.), `EncodingConfig` for handling different file encodings
- **Symbol models** - `ExtractedSymbol` for raw parse output, `SymbolVersion` for commit-tied records with deduplication keys
- **Statistics tracking** - `MiningStats` for progress reporting
- **Database layer** - `SymbolDatabase` with DuckDB schema, batched inserts, in-memory + on-conflict deduplication, and extraction state for resumability

## Project Structure

```
src/history_extractor/
├── __init__.py
├── database.py          # DuckDB schema + insert logic
└── models/
    ├── config.py        # ExtractionConfig, IgnorePatterns, EncodingConfig
    ├── symbol.py        # ExtractedSymbol, SymbolVersion
    └── stats.py         # MiningStats

scripts/
├── demo_models.py       # Demo: model instantiation and key generation
└── demo_database.py     # Demo: DB operations and deduplication

tests/
├── test_models.py       # Tests for all model classes
└── test_database.py     # Tests for database operations
```

## Setup

```bash
# Install dependencies
uv sync
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Demo Scripts

### Models Demo
Shows how the core data models work - ignore pattern matching, config creation, symbol key generation, and stats tracking.

```bash
uv run python scripts/demo_models.py
```

### Database Demo
Shows database operations - inserting symbols, querying, deduplication behavior, and extraction state for resumability.

```bash
uv run python scripts/demo_database.py
```
