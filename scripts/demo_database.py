#!/usr/bin/env python3
"""Demo: Initialize DB, insert records, query them."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from history_extractor.database import SymbolDatabase
from history_extractor.models.symbol import SymbolVersion


def create_sample_symbols() -> list[SymbolVersion]:
    """Create sample symbol versions for demo."""
    base_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)

    return [
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
        print(f"DB path: {db_path}\n")

        with SymbolDatabase(db_path) as db:
            print("Inserting sample symbols...")
            symbols = create_sample_symbols()
            for sym in symbols:
                added = db.add(sym)
                status = "added" if added else "duplicate"
                print(f"  {status}: {sym.symbol_key}")

            count = db.flush()
            print(f"\nFlushed {count} symbols to DB")

            print("\n--- Querying symbols ---")
            results = db.query(
                "SELECT symbol_key, kind, code_hash FROM symbol_versions"
            )
            for row in results:
                print(f"  {row[0]} ({row[1]}) -> {row[2]}")

            print("\n--- Stats ---")
            print(f"Total symbols: {db.get_symbol_count()}")
            print(f"Symbols in demo-repo: {db.get_symbol_count('demo-repo')}")

            print("\n--- Updating extraction state ---")
            db.update_state(
                repo_id="demo-repo",
                commit_hash="bbb222",
                commit_time=datetime.now(UTC),
                total_commits=2,
                total_symbols=4,
            )
            last = db.get_last_commit("demo-repo")
            print(f"Last processed commit: {last}")

            print("\n--- Duplicate handling ---")
            dup = symbols[0]
            added = db.add(dup)
            status = "added" if added else "skipped (in-memory)"
            print(f"Re-adding same symbol: {status}")
            db.flush()
            print(f"Total after re-add: {db.get_symbol_count()}")


if __name__ == "__main__":
    main()
