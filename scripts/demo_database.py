#!/usr/bin/env python3
"""Demo: Initialize DB, insert records, query them."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from codearc.database import SymbolDatabase
from codearc.mining.symbol_version import SymbolVersion


def create_sample_symbols() -> list[SymbolVersion]:
    """Create sample symbol versions for demo."""
    base_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)

    return [
        # Same function, two different versions (different code_hash)
        SymbolVersion(
            repo_id="demo-repo",
            commit_hash="aaa111",
            commit_time=base_time,
            file_path="src/utils.py",
            module="utils",
            name="helper",
            qualname="helper",
            kind="function",
            code="def helper(x): return x",
            code_hash="hash_v1",
            start_line=1,
            end_line=1,
        ),
        SymbolVersion(
            repo_id="demo-repo",
            commit_hash="bbb222",
            commit_time=base_time,
            file_path="src/utils.py",
            module="utils",
            name="helper",
            qualname="helper",
            kind="function",
            code="def helper(x): return x * 2",
            code_hash="hash_v2",
            start_line=1,
            end_line=1,
        ),
        # A class
        SymbolVersion(
            repo_id="demo-repo",
            commit_hash="aaa111",
            commit_time=base_time,
            file_path="src/models.py",
            module="models",
            name="User",
            qualname="User",
            kind="class",
            code="class User:\n    pass",
            code_hash="hash_user",
            start_line=5,
            end_line=6,
        ),
        # A method (qualname includes class name)
        SymbolVersion(
            repo_id="demo-repo",
            commit_hash="aaa111",
            commit_time=base_time,
            file_path="src/models.py",
            module="models",
            name="get_name",
            qualname="User.get_name",
            kind="function",
            code="def get_name(self): return self.name",
            code_hash="hash_method",
            start_line=8,
            end_line=8,
        ),
    ]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "demo.duckdb"
        print("=== Database Demo ===")
        print("SymbolDatabase manages DuckDB storage for extracted symbols.")
        print("It handles schema creation, batched inserts, and deduplication.")
        print(f"\nUsing temp DB: {db_path}\n")

        with SymbolDatabase(db_path) as db:
            print("--- Inserting Sample Symbols ---")
            print("We have 4 symbols: 2 versions of 'helper', a 'User' class,")
            print("and a 'User.get_name' method. Note they share symbol_key")
            print("but have different version_keys due to code_hash.\n")

            symbols = create_sample_symbols()
            for sym in symbols:
                added = db.add(sym)
                status = "added" if added else "duplicate"
                print(f"  {status}: {sym.symbol_key} (hash: {sym.code_hash})")

            print("\n--- Flushing to DB ---")
            print("db.add() stages symbols in memory. db.flush() writes to disk.")
            count = db.flush()
            print(f"Flushed {count} symbols to DB")

            print("\n--- Querying Symbols ---")
            print("Raw SQL queries work directly on the DuckDB connection.\n")
            results = db.query(
                "SELECT symbol_key, kind, code_hash FROM symbol_versions"
            )
            for row in results:
                print(f"  {row[0]} ({row[1]}) -> {row[2]}")

            print("\n--- Symbol Counts ---")
            print(f"Total symbols: {db.get_symbol_count()}")
            print(f"Symbols in demo-repo: {db.get_symbol_count('demo-repo')}")

            print("\n--- Extraction State ---")
            print("extraction_state table tracks progress for resumability.")
            print("After a crash, we can resume from the last processed commit.\n")
            db.update_state(
                repo_id="demo-repo",
                commit_hash="bbb222",
                commit_time=datetime.now(UTC),
                total_commits=2,
                total_symbols=4,
            )
            last = db.get_last_commit("demo-repo")
            print(f"Last processed commit: {last}")

            print("\n--- Duplicate Handling ---")
            print("Dedup happens at two levels:")
            print("  1. In-memory: same version_key in pending batch is skipped")
            print("  2. On insert: ON CONFLICT DO NOTHING handles DB duplicates\n")
            dup = symbols[0]
            added = db.add(dup)
            status = "added to pending" if added else "skipped (in-memory)"
            print(f"Re-adding symbol after flush: {status}")
            print("(It's 'added' because pending was cleared after flush)")
            db.flush()
            count = db.get_symbol_count()
            print(f"Total after re-add: {count} (unchanged - ON CONFLICT)")


if __name__ == "__main__":
    main()
