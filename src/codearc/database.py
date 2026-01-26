import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Self

import duckdb

from codearc.mining.symbol_version import SymbolVersion

logger = logging.getLogger(__name__)

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS symbol_versions (
    version_key TEXT PRIMARY KEY,
    symbol_key TEXT NOT NULL,
    repo_id TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    commit_time TIMESTAMP NOT NULL,
    file_path TEXT NOT NULL,
    module TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    kind TEXT NOT NULL,
    qualname TEXT NOT NULL,
    code TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    docstring TEXT,
    extra_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_symbol_key ON symbol_versions(symbol_key);
CREATE INDEX IF NOT EXISTS idx_commit_time ON symbol_versions(commit_time);
CREATE INDEX IF NOT EXISTS idx_repo_id ON symbol_versions(repo_id);

CREATE TABLE IF NOT EXISTS extraction_state (
    repo_id TEXT PRIMARY KEY,
    last_processed_commit TEXT NOT NULL,
    last_processed_time TIMESTAMP NOT NULL,
    total_commits_processed INTEGER DEFAULT 0,
    total_symbols_extracted INTEGER DEFAULT 0
);
"""

INSERT_SYMBOL_SQL = """
INSERT INTO symbol_versions (
    version_key, symbol_key, repo_id, commit_hash, commit_time,
    file_path, module, start_line, end_line, kind, qualname,
    code, code_hash, docstring, extra_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT DO NOTHING
"""

UPDATE_STATE_SQL = """
INSERT INTO extraction_state (
    repo_id, last_processed_commit, last_processed_time,
    total_commits_processed, total_symbols_extracted
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT (repo_id) DO UPDATE SET
    last_processed_commit = excluded.last_processed_commit,
    last_processed_time = excluded.last_processed_time,
    total_commits_processed = excluded.total_commits_processed,
    total_symbols_extracted = excluded.total_symbols_extracted
"""


class SymbolDatabase:
    """DuckDB database for storing extracted symbols."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn: duckdb.DuckDBPyConnection | None = None
        self._pending: OrderedDict[str, SymbolVersion] = OrderedDict()

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def connect(self) -> None:
        """Open database connection and ensure schema exists."""
        self.conn = duckdb.connect(str(self.db_path))
        self.conn.execute(SCHEMA_DDL)

    def close(self) -> None:
        """Flush pending writes and close connection."""
        if self._pending:
            self.flush()
        if self.conn:
            self.conn.close()
            self.conn = None

    def add(self, symbol: SymbolVersion) -> bool:
        """Add symbol to pending batch. Returns True if new, False if dup."""
        if symbol.version_key in self._pending:
            return False
        self._pending[symbol.version_key] = symbol
        return True

    def flush(self) -> int:
        """
        Write pending symbols to database.

        Returns the number of symbols attempted (not necessarily inserted,
        as ON CONFLICT DO NOTHING may skip duplicates already in the DB).
        """
        if not self._pending or not self.conn:
            return 0

        tuples = [s.to_db_tuple() for s in self._pending.values()]
        self.conn.executemany(INSERT_SYMBOL_SQL, tuples)
        self.conn.commit()

        count = len(self._pending)
        self._pending.clear()
        return count

    def update_state(
        self,
        repo_id: str,
        commit_hash: str,
        commit_time: datetime,
        total_commits: int,
        total_symbols: int,
    ) -> None:
        """Update extraction state for resumability."""
        if not self.conn:
            return

        self.conn.execute(
            UPDATE_STATE_SQL,
            [repo_id, commit_hash, commit_time, total_commits, total_symbols],
        )
        self.conn.commit()

    def get_last_commit(self, repo_id: str) -> str | None:
        """Get the last processed commit for a repo."""
        if not self.conn:
            return None

        result = self.conn.execute(
            "SELECT last_processed_commit FROM extraction_state WHERE repo_id = ?",
            [repo_id],
        ).fetchone()
        return result[0] if result else None

    def get_symbol_count(self, repo_id: str | None = None) -> int:
        """Get count of symbols, optionally filtered by repo."""
        if not self.conn:
            return 0

        if repo_id:
            result = self.conn.execute(
                "SELECT COUNT(*) FROM symbol_versions WHERE repo_id = ?",
                [repo_id],
            ).fetchone()
        else:
            result = self.conn.execute(
                "SELECT COUNT(*) FROM symbol_versions"
            ).fetchone()

        return result[0] if result else 0

    def query(self, sql: str, params: list | None = None) -> list[tuple]:
        """Execute arbitrary query and return results."""
        if not self.conn:
            return []
        return self.conn.execute(sql, params or []).fetchall()
