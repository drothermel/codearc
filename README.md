# history-extractor

Mine a Python repo's git history to extract all distinct versions of every function and class into a DuckDB database.

## Features

- **Configuration models** - `ExtractionConfig` for mining settings, `IgnorePatterns` for filtering files (venv, pycache, etc.), `EncodingConfig` for handling different file encodings
- **Symbol models** - `ExtractedSymbol` for raw parse output, `SymbolVersion` for commit-tied records with deduplication keys
- **Statistics tracking** - `MiningStats` for progress reporting
- **Database layer** - `SymbolDatabase` with DuckDB schema, batched inserts, in-memory + on-conflict deduplication, and extraction state for resumability
- **Utilities** - `compute_code_hash` for deduplication, `file_path_to_module` for converting paths to Python module names, `safe_decode` for handling different file encodings
- **Symbol extraction** - LibCST-based parser that extracts functions, classes, and methods with qualified names, docstrings, and line numbers. Handles nested classes, skips nested functions, and gracefully handles syntax errors.

## Setup

```bash
uv sync
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Project Structure

```
src/history_extractor/
├── __init__.py
├── database.py          # DuckDB schema + insert logic
├── extractor.py         # LibCST symbol extraction
├── miner.py             # PyDriller git traversal
├── utils.py             # Hashing, module paths, encoding
└── models/
    ├── encoding_config.py       # EncodingConfig
    ├── extracted_symbol.py      # ExtractedSymbol, SymbolKind
    ├── extraction_config.py     # ExtractionConfig
    ├── ignore_patterns.py       # IgnorePatterns
    ├── mining_stats.py          # MiningStats
    └── symbol_version.py        # SymbolVersion

scripts/
├── demo_models.py       # Demo: model instantiation and key generation
├── demo_database.py     # Demo: DB operations and deduplication
├── demo_extractor.py    # Demo: parsing Python code and extracting symbols
├── demo_module_paths.py # Demo: module path resolution for different layouts
└── demo_miner.py        # Demo: mining a git repo and querying results

tests/
├── test_models.py       # Tests for all model classes
├── test_database.py     # Tests for database operations
├── test_extractor.py    # Tests for symbol extraction
├── test_utils.py        # Tests for utility functions
└── test_miner.py        # Tests for git mining
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

### Extractor Demo

Shows how LibCST parses Python code and extracts functions, classes, and methods with their qualified names and metadata.

```bash
uv run python scripts/demo_extractor.py
```

### Module Paths Demo

Shows how file paths are converted to Python module names for different project layouts (simple, src/, explicit package root).

```bash
uv run python scripts/demo_module_paths.py
```

### Miner Demo
Creates a sample git repository, mines it for symbols across commits, and shows version history and query examples.

```bash
uv run python scripts/demo_miner.py
```
