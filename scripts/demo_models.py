#!/usr/bin/env python3
"""Demo: Create model instances and show key generation."""

from datetime import UTC, datetime
from pathlib import Path

from history_extractor.models.config import ExtractionConfig, IgnorePatterns
from history_extractor.models.stats import MiningStats
from history_extractor.models.symbol import ExtractedSymbol, SymbolVersion


def demo_ignore_patterns() -> None:
    print("=== Ignore Patterns ===")
    patterns = IgnorePatterns()

    test_paths = [
        "src/main.py",
        "venv/lib/python3.12/site.py",
        ".venv/bin/activate",
        "proto/api_pb2.py",
        "tests/test_foo.py",
        "__pycache__/foo.cpython-312.pyc",
    ]

    for path in test_paths:
        matched = patterns.matches(path)
        status = "IGNORE" if matched else "process"
        print(f"  {status:8} {path}")
    print()


def demo_extraction_config() -> None:
    print("=== Extraction Config ===")
    config = ExtractionConfig(
        repo_path=Path("/home/user/my-project"),
        db_path=Path("/tmp/symbols.duckdb"),
        authors=["alice", "bob"],
        skip_merge_commits=True,
    )
    print(f"  Repo path: {config.repo_path}")
    print(f"  Repo ID (derived): {config.get_repo_id()}")
    print(f"  Authors filter: {config.authors}")
    print(f"  Skip merges: {config.skip_merge_commits}")
    print()


def demo_symbol_keys() -> None:
    print("=== Symbol Keys ===")
    version = SymbolVersion(
        repo_id="my-project",
        commit_hash="a1b2c3d4e5f6",
        commit_time=datetime(2024, 6, 15, 14, 30, 0, tzinfo=UTC),
        file_path="src/utils/helpers.py",
        module="utils.helpers",
        name="process_data",
        qualname="DataProcessor.process_data",
        kind="function",
        code="def process_data(self, x): return x * 2",
        code_hash="abc123def456",
        start_line=42,
        end_line=43,
        docstring="Process the input data.",
    )

    print(f"  Name: {version.name}")
    print(f"  Qualname: {version.qualname}")
    print(f"  Symbol Key: {version.symbol_key}")
    print(f"  Version Key: {version.version_key}")
    print()


def demo_extracted_symbol() -> None:
    print("=== Extracted Symbol ===")
    symbol = ExtractedSymbol(
        name="calculate",
        qualname="MathUtils.calculate",
        kind="function",
        code="def calculate(self, a, b):\n    return a + b",
        start_line=10,
        end_line=11,
        docstring="Add two numbers.",
    )
    print(f"  Name: {symbol.name}")
    print(f"  Qualname: {symbol.qualname}")
    print(f"  Kind: {symbol.kind}")
    print(f"  Lines: {symbol.start_line}-{symbol.end_line}")
    print(f"  Docstring: {symbol.docstring}")
    print()


def demo_stats() -> None:
    print("=== Mining Stats ===")
    stats = MiningStats()
    stats.increment_commits_processed()
    stats.increment_commits_processed()
    stats.increment_commits_processed()
    stats.increment_files_processed()
    stats.increment_files_processed()
    stats.add_symbols(15)
    stats.increment_parse_errors()

    print(stats.summary())
    print()


if __name__ == "__main__":
    demo_ignore_patterns()
    demo_extraction_config()
    demo_symbol_keys()
    demo_extracted_symbol()
    demo_stats()
