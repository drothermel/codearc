import logging
from datetime import datetime

from pydriller import Commit, Repository

from codearc.database import SymbolDatabase
from codearc.extraction.extract_symbols import extract_symbols
from codearc.mining.mining_config import MiningConfig
from codearc.mining.mining_stats import MiningStats
from codearc.mining.symbol_version import SymbolVersion
from codearc.models.extracted_symbol import ExtractedSymbol
from codearc.utils import (
    compute_code_hash,
    ensure_utc,
    file_path_to_module,
    safe_decode,
)

logger = logging.getLogger(__name__)


def mine_repository(config: MiningConfig, db: SymbolDatabase) -> MiningStats:
    """
    Mine a git repository for symbol versions.

    Traverses commit history, extracts symbols from Python files,
    and stores them in the database. Commits to DB after each git commit
    for crash safety.
    """
    stats = MiningStats()
    repo_id = config.effective_repo_id

    repo = Repository(str(config.repo_path), **config.to_pydriller_kwargs())

    for commit in repo.traverse_commits():
        _process_commit(
            commit=commit,
            config=config,
            db=db,
            repo_id=repo_id,
            stats=stats,
        )

        # Flush and update state after each commit for crash safety
        flushed = db.flush()
        if flushed > 0:
            stats.add_deduplicated(flushed)

        stats.increment_commits_processed()

        db.update_state(
            repo_id=repo_id,
            commit_hash=commit.hash,
            commit_time=ensure_utc(commit.committer_date),
            total_commits=stats.commits_processed,
            total_symbols=stats.symbols_extracted,
        )

    return stats


def _decode_source(
    source: str | bytes,
    encodings: list[str],
    file_path: str,
    commit_hash: str,
    stats: MiningStats,
) -> str | None:
    """Decode source bytes, returning None on encoding failure."""
    if isinstance(source, str):
        return source
    decoded = safe_decode(source, encodings)
    if decoded is None:
        logger.warning("Failed to decode %s in %s", file_path, commit_hash[:8])
        stats.increment_encoding_errors()
    return decoded


def _create_symbol_version(
    sym: ExtractedSymbol,
    *,
    repo_id: str,
    commit_hash: str,
    commit_time: datetime,
    file_path: str,
    module: str,
) -> SymbolVersion:
    """Convert an ExtractedSymbol to a SymbolVersion for DB storage."""
    return SymbolVersion(
        repo_id=repo_id,
        commit_hash=commit_hash,
        commit_time=commit_time,
        file_path=file_path,
        module=module,
        name=sym.name,
        qualname=sym.qualname,
        kind=sym.kind,
        code=sym.code,
        code_hash=compute_code_hash(sym.code),
        start_line=sym.start_line,
        end_line=sym.end_line,
        docstring=sym.docstring,
    )


def _process_commit(
    commit: Commit,
    config: MiningConfig,
    db: SymbolDatabase,
    repo_id: str,
    stats: MiningStats,
) -> None:
    """Process a single commit, extracting symbols from modified Python files."""
    commit_time = ensure_utc(commit.committer_date)

    for mod in commit.modified_files:
        # Skip non-Python files (should be filtered by PyDriller, but double-check)
        if not mod.filename.endswith(".py"):
            continue

        # Skip deleted files
        if mod.source_code is None:
            continue

        file_path = mod.new_path or mod.old_path
        if not file_path:
            continue

        # Check ignore patterns
        if config.ignore_patterns.matches(file_path):
            stats.increment_files_skipped()
            continue

        # Decode source code
        source = _decode_source(
            mod.source_code,
            config.encoding_config.encodings,
            file_path,
            commit.hash,
            stats,
        )
        if source is None:
            continue

        # Extract symbols
        symbols = extract_symbols(source)
        if not symbols:
            # Could be empty file, only imports, or parse error
            # extract_symbols logs parse errors internally
            stats.increment_files_processed()
            continue

        # Convert to SymbolVersion and add to DB
        try:
            module = file_path_to_module(
                file_path,
                config.repo_path,
                config.package_root,
            )
        except ValueError:
            # File is outside package root (e.g., tests/, scripts/)
            # Skip since we only extract from package code
            stats.increment_files_processed()
            continue

        for sym in symbols:
            version = _create_symbol_version(
                sym,
                repo_id=repo_id,
                commit_hash=commit.hash,
                commit_time=commit_time,
                file_path=file_path,
                module=module,
            )
            db.add(version)
            stats.add_symbols(1)

        stats.increment_files_processed()
