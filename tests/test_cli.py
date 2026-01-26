import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codearc.cli import app
from codearc.database import SymbolDatabase

runner = CliRunner()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with commits."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

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

    (repo_path / "utils.py").write_text("def helper(x):\n    return x\n")
    subprocess.run(["git", "add", "utils.py"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add helper"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    (repo_path / "models.py").write_text("class User:\n    pass\n")
    subprocess.run(["git", "add", "models.py"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add User class"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    return repo_path


class TestCliHelp:
    def test_help_shows_usage(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output
        assert "--db" in result.output
        assert "--verbose" in result.output


class TestCliExtract:
    def test_extract_creates_database(self, git_repo: Path, tmp_path: Path) -> None:
        db_path = tmp_path / "output.duckdb"

        result = runner.invoke(app, ["--repo", str(git_repo), "--db", str(db_path)])

        assert result.exit_code == 0
        assert db_path.exists()

    def test_extract_populates_symbols(self, git_repo: Path, tmp_path: Path) -> None:
        db_path = tmp_path / "output.duckdb"

        result = runner.invoke(app, ["--repo", str(git_repo), "--db", str(db_path)])
        assert result.exit_code == 0, result.output

        with SymbolDatabase(db_path) as db:
            count = db.get_symbol_count()

        assert count >= 2  # helper function + User class

    def test_extract_verbose_shows_stats(self, git_repo: Path, tmp_path: Path) -> None:
        db_path = tmp_path / "output.duckdb"

        result = runner.invoke(
            app, ["--repo", str(git_repo), "--db", str(db_path), "--verbose"]
        )

        assert result.exit_code == 0
        assert "Commits:" in result.output
        assert "Symbols:" in result.output

    def test_extract_with_ignore_pattern(self, git_repo: Path, tmp_path: Path) -> None:
        db_path = tmp_path / "output.duckdb"

        result = runner.invoke(
            app,
            [
                "--repo",
                str(git_repo),
                "--db",
                str(db_path),
                "--ignore",
                "models.py",
            ],
        )

        assert result.exit_code == 0

        with SymbolDatabase(db_path) as db:
            results = db.query("SELECT * FROM symbol_versions WHERE qualname = 'User'")

        assert len(results) == 0  # User class should be ignored

    def test_extract_with_authors_filter(self, git_repo: Path, tmp_path: Path) -> None:
        db_path = tmp_path / "output.duckdb"

        result = runner.invoke(
            app,
            [
                "--repo",
                str(git_repo),
                "--db",
                str(db_path),
                "--authors",
                "Nonexistent Author",
            ],
        )

        assert result.exit_code == 0

        with SymbolDatabase(db_path) as db:
            count = db.get_symbol_count()

        assert count == 0  # No commits from this author

    def test_extract_with_empty_authors_extracts_all(
        self, git_repo: Path, tmp_path: Path
    ) -> None:
        """Empty or whitespace-only authors should not filter commits."""
        db_path = tmp_path / "output.duckdb"

        result = runner.invoke(
            app,
            [
                "--repo",
                str(git_repo),
                "--db",
                str(db_path),
                "--authors",
                "  ",  # Whitespace-only
            ],
        )

        assert result.exit_code == 0

        with SymbolDatabase(db_path) as db:
            count = db.get_symbol_count()

        assert count >= 2  # Should extract all, not filter to empty

    def test_extract_invalid_repo_fails(self, tmp_path: Path) -> None:
        db_path = tmp_path / "output.duckdb"
        fake_repo = tmp_path / "not_a_repo"
        fake_repo.mkdir()

        result = runner.invoke(app, ["--repo", str(fake_repo), "--db", str(db_path)])

        assert result.exit_code != 0

    def test_missing_required_args(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()
