import logging
from datetime import UTC, datetime

from pydriller import Repository

from history_extractor.database import SymbolDatabase
from history_extractor.extractor import extract_symbols
from history_extractor.models.config import ExtractionConfig
from history_extractor.models.stats import MiningStats
from history_extractor.models.symbol import SymbolVersion
from history_extractor.utils import compute_code_hash, file_path_to_module, safe_decode

logger = logging.getLogger(__name__)


def mine_repository(config: ExtractionConfig, db: SymbolDatabase) -> MiningStats:
    """
    Mine a git repository for symbol versions.

    Traverses commit history, extracts symbols from Python files,
    and stores them in the database. Commits to DB after each git commit
    for crash safety.
    """
    stats = MiningStats()
    repo_id = config.get_repo_id()

    # Build PyDriller options
    repo_kwargs: dict = {
        "only_modifications_with_file_types": [".py"],
    }

    if config.since_commit:
        repo_kwargs["from_commit"] = config.since_commit
    if config.since_date:
        repo_kwargs["since"] = config.since_date
    if config.authors:
        repo_kwargs["only_authors"] = config.authors
    if config.skip_merge_commits:
        repo_kwargs["only_no_merge"] = True

    repo = Repository(str(config.repo_path), **repo_kwargs)

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

        db.update_state(
            repo_id=repo_id,
            commit_hash=commit.hash,
            commit_time=_ensure_utc(commit.committer_date),
            total_commits=stats.commits_processed,
            total_symbols=stats.symbols_extracted,
        )

        stats.increment_commits_processed()

    return stats


def _process_commit(
    commit,
    config: ExtractionConfig,
    db: SymbolDatabase,
    repo_id: str,
    stats: MiningStats,
) -> None:
    """Process a single commit, extracting symbols from modified Python files."""
    commit_time = _ensure_utc(commit.committer_date)

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
        source = mod.source_code
        if isinstance(source, bytes):
            decoded = safe_decode(source, config.encoding_config.encodings)
            if decoded is None:
                logger.warning("Failed to decode %s in %s", file_path, commit.hash[:8])
                stats.increment_encoding_errors()
                continue
            source = decoded

        # Extract symbols
        symbols = extract_symbols(source)
        if not symbols:
            # Could be empty file, only imports, or parse error
            # extract_symbols logs parse errors internally
            stats.increment_files_processed()
            continue

        # Convert to SymbolVersion and add to DB
        module = file_path_to_module(
            file_path,
            config.repo_path,
            config.package_root,
        )

        for sym in symbols:
            code_hash = compute_code_hash(sym.code)
            version = SymbolVersion(
                repo_id=repo_id,
                commit_hash=commit.hash,
                commit_time=commit_time,
                file_path=file_path,
                module=module,
                name=sym.name,
                qualname=sym.qualname,
                kind=sym.kind,
                code=sym.code,
                code_hash=code_hash,
                start_line=sym.start_line,
                end_line=sym.end_line,
                docstring=sym.docstring,
            )
            db.add(version)
            stats.add_symbols(1)

        stats.increment_files_processed()


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
