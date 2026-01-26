import subprocess
from pathlib import Path

import pytest

from codearc.database import SymbolDatabase
from codearc.mining.ignore_patterns import IgnorePatterns
from codearc.mining.miner import mine_repository
from codearc.mining.mining_config import MiningConfig


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with some commits."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Commit 1: Add a function
    (repo_path / "utils.py").write_text("def helper(x):\n    return x\n")
    subprocess.run(["git", "add", "utils.py"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add helper function"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Commit 2: Modify the function
    (repo_path / "utils.py").write_text("def helper(x):\n    return x * 2\n")
    subprocess.run(["git", "add", "utils.py"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Update helper function"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Commit 3: Add a class
    (repo_path / "models.py").write_text(
        "class User:\n    def get_name(self):\n        return self.name\n"
    )
    subprocess.run(["git", "add", "models.py"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add User class"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    return repo_path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.duckdb"


class TestMineRepository:
    def test_basic_mining(self, git_repo: Path, db_path: Path) -> None:
        config = MiningConfig(repo_path=git_repo, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            stats = mine_repository(config, db)

        assert stats.commits_processed == 3
        assert stats.files_processed >= 3  # utils.py twice, models.py once
        assert stats.symbols_extracted >= 4  # helper x2, User, get_name

        # Verify DB contents
        with SymbolDatabase(db_path) as db:
            count = db.get_symbol_count()
            assert count >= 4

    def test_extracts_different_versions(self, git_repo: Path, db_path: Path) -> None:
        config = MiningConfig(repo_path=git_repo, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            mine_repository(config, db)

        # Query for helper function versions
        with SymbolDatabase(db_path) as db:
            results = db.query(
                "SELECT code_hash, code FROM symbol_versions "
                "WHERE qualname = 'helper' ORDER BY commit_time"
            )

        assert len(results) == 2
        # Different code hashes for different versions
        assert results[0][0] != results[1][0]
        assert "return x\n" in results[0][1]
        assert "return x * 2" in results[1][1]

    def test_extracts_methods_with_qualname(
        self, git_repo: Path, db_path: Path
    ) -> None:
        config = MiningConfig(repo_path=git_repo, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            mine_repository(config, db)

        with SymbolDatabase(db_path) as db:
            results = db.query(
                "SELECT qualname FROM symbol_versions WHERE qualname = 'User.get_name'"
            )

        assert len(results) == 1
        assert results[0][0] == "User.get_name"

    def test_ignore_patterns(self, git_repo: Path, db_path: Path) -> None:
        # Add a file that should be ignored
        venv_dir = git_repo / "venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "ignored.py").write_text("def should_ignore(): pass\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add venv file"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        config = MiningConfig(repo_path=git_repo, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            stats = mine_repository(config, db)

        # Verify ignored file was skipped
        assert stats.files_skipped >= 1

        with SymbolDatabase(db_path) as db:
            results = db.query(
                "SELECT * FROM symbol_versions WHERE qualname = 'should_ignore'"
            )
        assert len(results) == 0

    def test_custom_ignore_patterns(self, git_repo: Path, db_path: Path) -> None:
        # Add a generated file
        (git_repo / "generated.py").write_text("def generated_func(): pass\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add generated file"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        config = MiningConfig(
            repo_path=git_repo,
            db_path=db_path,
            ignore_patterns=IgnorePatterns(patterns=["generated.py"]),
        )

        with SymbolDatabase(db_path) as db:
            mine_repository(config, db)

        with SymbolDatabase(db_path) as db:
            results = db.query(
                "SELECT * FROM symbol_versions WHERE qualname = 'generated_func'"
            )
        assert len(results) == 0

    def test_extraction_state_updated(self, git_repo: Path, db_path: Path) -> None:
        config = MiningConfig(repo_path=git_repo, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            mine_repository(config, db)

        with SymbolDatabase(db_path) as db:
            last_commit = db.get_last_commit("test_repo")

        assert last_commit is not None
        assert len(last_commit) == 40  # Full SHA

    def test_extraction_state_commit_count_matches_stats(
        self, git_repo: Path, db_path: Path
    ) -> None:
        """Verify persisted commit count matches returned stats (no off-by-one)."""
        config = MiningConfig(repo_path=git_repo, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            stats = mine_repository(config, db)

        with SymbolDatabase(db_path) as db:
            result = db.query(
                "SELECT total_commits_processed FROM extraction_state "
                "WHERE repo_id = ?",
                ["test_repo"],
            )

        assert len(result) == 1
        persisted_count = result[0][0]
        assert persisted_count == stats.commits_processed
        assert persisted_count == 3  # Sanity check: we created 3 commits

    def test_repo_id_from_config(self, git_repo: Path, db_path: Path) -> None:
        config = MiningConfig(
            repo_path=git_repo,
            db_path=db_path,
            repo_id="custom-repo-id",
        )

        with SymbolDatabase(db_path) as db:
            mine_repository(config, db)

        with SymbolDatabase(db_path) as db:
            results = db.query("SELECT DISTINCT repo_id FROM symbol_versions")

        assert len(results) == 1
        assert results[0][0] == "custom-repo-id"

    def test_handles_syntax_errors(self, git_repo: Path, db_path: Path) -> None:
        # Add a file with syntax error
        (git_repo / "broken.py").write_text("def broken(\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add broken file"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        config = MiningConfig(repo_path=git_repo, db_path=db_path)

        # Should not raise
        with SymbolDatabase(db_path) as db:
            stats = mine_repository(config, db)

        # Other files should still be processed
        assert stats.commits_processed == 4
        assert stats.symbols_extracted >= 4

    def test_empty_repo(self, tmp_path: Path, db_path: Path) -> None:
        # Create empty repo
        repo_path = tmp_path / "empty_repo"
        repo_path.mkdir()
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

        config = MiningConfig(repo_path=repo_path, db_path=db_path)

        with SymbolDatabase(db_path) as db:
            stats = mine_repository(config, db)

        assert stats.commits_processed == 0
        assert stats.symbols_extracted == 0
