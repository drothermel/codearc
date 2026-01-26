from datetime import UTC, datetime
from pathlib import Path

import pytest

from codearc.database import SymbolDatabase
from codearc.mining.symbol_version import SymbolVersion


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.duckdb"


@pytest.fixture
def sample_symbol() -> SymbolVersion:
    return SymbolVersion(
        repo_id="test-repo",
        commit_hash="abc123",
        commit_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        file_path="src/foo.py",
        module="foo",
        name="bar",
        qualname="bar",
        kind="function",
        code="def bar(): pass",
        code_hash="deadbeef",
        start_line=1,
        end_line=1,
    )


class TestSymbolDatabase:
    def test_create_schema(self, db_path: Path) -> None:
        with SymbolDatabase(db_path) as db:
            tables = db.query(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            )
            table_names = {t[0] for t in tables}
            assert "symbol_versions" in table_names
            assert "extraction_state" in table_names

    def test_add_and_flush(self, db_path: Path, sample_symbol: SymbolVersion) -> None:
        with SymbolDatabase(db_path) as db:
            added = db.add(sample_symbol)
            assert added is True
            count = db.flush()
            assert count == 1
            assert db.get_symbol_count() == 1

    def test_add_duplicate_in_memory(
        self, db_path: Path, sample_symbol: SymbolVersion
    ) -> None:
        with SymbolDatabase(db_path) as db:
            assert db.add(sample_symbol) is True
            assert db.add(sample_symbol) is False
            count = db.flush()
            assert count == 1

    def test_duplicate_on_conflict(
        self, db_path: Path, sample_symbol: SymbolVersion
    ) -> None:
        with SymbolDatabase(db_path) as db:
            db.add(sample_symbol)
            db.flush()
            db.add(sample_symbol)
            db.flush()
            assert db.get_symbol_count() == 1

    def test_update_and_get_state(self, db_path: Path) -> None:
        with SymbolDatabase(db_path) as db:
            commit_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
            db.update_state("test-repo", "abc123", commit_time, 10, 100)
            last = db.get_last_commit("test-repo")
            assert last == "abc123"

    def test_get_last_commit_not_found(self, db_path: Path) -> None:
        with SymbolDatabase(db_path) as db:
            last = db.get_last_commit("nonexistent")
            assert last is None

    def test_symbol_count_by_repo(self, db_path: Path) -> None:
        with SymbolDatabase(db_path) as db:
            sym1 = SymbolVersion(
                repo_id="repo-a",
                commit_hash="abc",
                commit_time=datetime.now(UTC),
                file_path="a.py",
                module="a",
                name="f",
                qualname="f",
                kind="function",
                code="def f(): pass",
                code_hash="hash1",
                start_line=1,
                end_line=1,
            )
            sym2 = SymbolVersion(
                repo_id="repo-b",
                commit_hash="def",
                commit_time=datetime.now(UTC),
                file_path="b.py",
                module="b",
                name="g",
                qualname="g",
                kind="function",
                code="def g(): pass",
                code_hash="hash2",
                start_line=1,
                end_line=1,
            )
            db.add(sym1)
            db.add(sym2)
            db.flush()

            assert db.get_symbol_count() == 2
            assert db.get_symbol_count("repo-a") == 1
            assert db.get_symbol_count("repo-b") == 1
