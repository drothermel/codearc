#!/usr/bin/env python3
"""Demo: Mine a git repository and explore the results."""

import subprocess
import tempfile
from pathlib import Path

from codearc.database import SymbolDatabase
from codearc.mining.miner import mine_repository
from codearc.mining.mining_config import MiningConfig


def create_sample_repo(repo_path: Path) -> None:
    """Create a sample git repository with some history."""
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "demo@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Demo User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Commit 1: Initial version
    (repo_path / "calculator.py").write_text(
        '''
def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    return a - b
'''.lstrip()
    )
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial calculator functions"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Commit 2: Add multiply
    (repo_path / "calculator.py").write_text(
        '''
def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    return a - b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b
'''.lstrip()
    )
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add multiply function"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Commit 3: Refactor add with type hints
    (repo_path / "calculator.py").write_text(
        '''
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    return a - b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b
'''.lstrip()
    )
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add type hints to add function"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Commit 4: Add a class
    (repo_path / "models.py").write_text(
        '''
class Calculator:
    """A calculator class."""

    def __init__(self, precision: int = 2):
        self.precision = precision

    def divide(self, a: float, b: float) -> float:
        """Divide a by b with configured precision."""
        return round(a / b, self.precision)
'''.lstrip()
    )
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add Calculator class"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )


def main() -> None:
    print("=== Miner Demo ===")
    print("The miner traverses git history, extracts symbols from each commit,")
    print("and stores them in a DuckDB database.\n")

    with tempfile.TemporaryDirectory() as tmp:
        repo_path = Path(tmp) / "sample_repo"
        db_path = Path(tmp) / "symbols.duckdb"

        print("--- Creating Sample Repository ---")
        create_sample_repo(repo_path)
        print(f"Created repo at: {repo_path}")

        # Show git log
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        print("\nGit history:")
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")

        print("\n--- Mining Repository ---")
        config = MiningConfig(repo_path=repo_path, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            stats = mine_repository(config, db)

        print("\nMining complete!")
        print(stats.summary())

        print("\n--- Querying Results ---")
        with SymbolDatabase(db_path) as db:
            # Show all unique symbols
            print("\nUnique symbols extracted:")
            results = db.query(
                "SELECT DISTINCT symbol_key, kind FROM symbol_versions ORDER BY kind"
            )
            for row in results:
                print(f"  [{row[1]:8}] {row[0]}")

            # Show version history for 'add' function
            print("\n\nVersion history for 'add' function:")
            results = db.query(
                "SELECT commit_hash, code_hash, code FROM symbol_versions "
                "WHERE qualname = 'add' ORDER BY commit_time"
            )
            for i, row in enumerate(results, 1):
                print(f"\n  Version {i} (commit {row[0][:8]}, hash {row[1][:8]}):")
                first_line = row[2].strip().split("\n")[0]
                print(f"    {first_line}")

            # Show symbols per commit
            print("\n\nSymbols extracted per commit:")
            results = db.query(
                "SELECT commit_hash, COUNT(*) as cnt "
                "FROM symbol_versions GROUP BY commit_hash ORDER BY cnt DESC"
            )
            for row in results:
                print(f"  {row[0][:8]}: {row[1]} symbols")

            # Total stats
            print(f"\n\nTotal symbol versions in DB: {db.get_symbol_count()}")


if __name__ == "__main__":
    main()
