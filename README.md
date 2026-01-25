# history-extractor

Mine a Python repo's git history to extract all distinct versions of every function and class into a DuckDB database.

## Usage

```bash
history-extractor --repo /path/to/repo --db output.duckdb [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--repo PATH` | Path to the git repository (required) |
| `--db PATH` | Path to output DuckDB file (required) |
| `--package-root PATH` | Package root for module path calculation |
| `--since-commit HASH` | Resume from a specific commit |
| `--since DATE` | Process commits after date (ISO format) |
| `--authors "a,b"` | Comma-separated author filter |
| `--no-merge/--include-merge` | Skip merge commits (default: skip) |
| `--ignore PATTERN` | Additional ignore patterns (repeatable) |
| `-v, --verbose` | Show mining statistics |

### Example

```bash
# Mine a repo with verbose output
history-extractor --repo ~/projects/mylib --db mylib.duckdb --verbose

# Filter by author and date
history-extractor --repo . --db output.duckdb --authors "Alice,Bob" --since 2024-01-01
```

## Current Functionality

**Phase 1 (Core Infrastructure)** is complete:

## Setup

```bash
uv sync
```

## Running Tests

```bash
uv run pytest tests/ -v
```

**Phase 4 (CLI)** is complete:

- **Typer CLI** - `history-extractor` command with all options for repo mining
- **Rich output** - Statistics display with `--verbose` flag

## Project Structure

```
src/history_extractor/
├── __init__.py
├── cli.py               # Typer CLI entrypoint
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
├── test_cli.py          # Tests for CLI
├── test_database.py     # Tests for database operations
├── test_extractor.py    # Tests for symbol extraction
├── test_miner.py        # Tests for git mining
├── test_models.py       # Tests for all model classes
└── test_utils.py        # Tests for utility functions
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
