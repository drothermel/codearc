# codearc

Mine a Python repo's git history to extract all distinct versions of every function and class into a DuckDB database.

## Quick Start

```bash
# Run directly (no install needed)
uvx codearc --repo /path/to/repo --db output.duckdb --verbose

# Query the results
python -c "
import duckdb
conn = duckdb.connect('output.duckdb')
for row in conn.execute('SELECT qualname, kind, COUNT(*) as versions FROM symbol_versions GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10').fetchall():
    print(row)
"
```

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# As a CLI tool
uv tool install codearc
codearc --repo /path/to/repo --db output.duckdb

# As a library
uv add codearc
```

### From source

```bash
git clone https://github.com/drothermel/codearc.git
cd codearc
uv sync
uv run codearc --help
```

## CLI Reference

```bash
codearc --repo PATH --db OUTPUT.duckdb [options]
```

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

### Examples

```bash
# Mine a repo with verbose output
codearc --repo ~/projects/mylib --db mylib.duckdb --verbose

# Filter by author and date
codearc --repo . --db output.duckdb --authors "Alice,Bob" --since 2024-01-01

# Resume from a specific commit
codearc --repo . --db output.duckdb --since-commit abc123

# Add custom ignore patterns
codearc --repo . --db output.duckdb --ignore "generated/*" --ignore "vendor/*"
```

## Features

- **Symbol extraction** - Extracts functions, classes, and methods using LibCST with accurate source positions and qualified names
- **Version deduplication** - Stores only distinct versions of each symbol (by content hash), avoiding redundant storage
- **Git history traversal** - Walks commit history with PyDriller, processing only modified Python files
- **Crash recovery** - Per-commit database writes with extraction state tracking for resumability
- **Flexible filtering** - Filter by author, date, ignore patterns; skip merge commits by default
- **Encoding handling** - Gracefully handles non-UTF8 files with fallback encodings

## Database Schema

The extracted data is stored in two tables:

**`symbol_versions`** - All distinct versions of symbols
- `version_key` - Unique identifier (repo:module:qualname:kind:code_hash)
- `symbol_key` - Symbol identifier without version (repo:module:qualname:kind)
- `repo_id`, `commit_hash`, `commit_time` - Git metadata
- `file_path`, `module`, `start_line`, `end_line` - Location info
- `kind` - "function" or "class"
- `qualname` - Qualified name (e.g., `ClassName.method_name`)
- `code`, `code_hash` - Exact source code and its hash
- `docstring` - Extracted docstring if present

**`extraction_state`** - Tracks mining progress for resumability
- `repo_id`, `last_processed_commit`, `total_commits_processed`, etc.

## Demo Scripts

Interactive demos to explore the library's capabilities:

| Script | Description |
|--------|-------------|
| `scripts/demo_models.py` | Data models, ignore pattern matching, key generation |
| `scripts/demo_database.py` | Database operations, deduplication, extraction state |
| `scripts/demo_extractor.py` | LibCST parsing, symbol extraction with metadata |
| `scripts/demo_module_paths.py` | File path to module name conversion |
| `scripts/demo_miner.py` | End-to-end mining of a sample git repo |

Run any demo:

```bash
uv run python scripts/demo_miner.py
```

## Development

### Running Tests

```bash
uv run pytest tests/ -v
```

### Project Structure

```text
src/codearc/
├── cli.py               # Typer CLI entrypoint
├── database.py          # DuckDB schema + operations
├── utils.py             # Hashing, module paths, encoding
├── extraction/          # Symbol extraction from source
│   ├── extract_symbols.py   # Main extraction entry point
│   ├── symbol_extractor.py  # LibCST visitor for symbols
│   └── docstring.py         # Docstring extraction
├── mining/              # Git history mining
│   ├── miner.py             # PyDriller git traversal
│   ├── mining_config.py     # MiningConfig
│   ├── mining_stats.py      # MiningStats
│   ├── symbol_version.py    # SymbolVersion
│   ├── ignore_patterns.py   # IgnorePatterns
│   └── encoding_config.py   # EncodingConfig
└── models/              # Shared models
    └── extracted_symbol.py  # ExtractedSymbol, SymbolKind

scripts/                 # Demo scripts
tests/                   # Test suite (80 tests)
```

### Dependencies

- **PyDriller** - Git repository mining
- **LibCST** - Lossless Python parsing
- **DuckDB** - Embedded analytics database
- **Typer** - CLI framework
- **Rich** - Terminal output formatting
- **Pydantic** - Data validation and models
