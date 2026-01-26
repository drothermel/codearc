import logging
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from codearc.database import SymbolDatabase
from codearc.mining.ignore_patterns import IgnorePatterns
from codearc.mining.miner import mine_repository
from codearc.mining.mining_config import MiningConfig

app = typer.Typer(
    name="codearc",
    help="Mine a Python repo's git history to extract symbol versions into DuckDB.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def extract(
    repo: Path = typer.Option(
        ...,
        "--repo",
        help="Path to the git repository to mine.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    db: Path = typer.Option(
        ...,
        "--db",
        help="Path to the output DuckDB file.",
        resolve_path=True,
    ),
    package_root: Path | None = typer.Option(
        None,
        "--package-root",
        help="Package root for module path calculation.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    since_commit: str | None = typer.Option(
        None,
        "--since-commit",
        help="Process commits starting from this commit hash.",
    ),
    since_date: datetime | None = typer.Option(
        None,
        "--since",
        help="Process commits after this date (ISO format).",
        formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"],
    ),
    authors: str | None = typer.Option(
        None,
        "--authors",
        help="Comma-separated list of authors to filter by.",
    ),
    no_merge: bool = typer.Option(
        True,
        "--no-merge/--include-merge",
        help="Skip merge commits (default: skip).",
    ),
    ignore: list[str] | None = typer.Option(
        None,
        "--ignore",
        help="Additional ignore patterns (can be repeated).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show mining statistics.",
    ),
) -> None:
    """Extract symbol versions from a git repository's history."""
    if verbose:
        logging.basicConfig(level=logging.INFO)

    author_list = None
    if authors and authors.strip():
        author_list = [a.strip() for a in authors.split(",") if a.strip()] or None

    ignore_patterns = IgnorePatterns()
    if ignore:
        ignore_patterns = IgnorePatterns(patterns=ignore_patterns.patterns + ignore)

    config = MiningConfig(
        repo_path=repo,
        db_path=db,
        package_root=package_root,
        since_commit=since_commit,
        since_date=since_date,
        authors=author_list,
        skip_merge_commits=no_merge,
        ignore_patterns=ignore_patterns,
    )

    try:
        with SymbolDatabase(db) as database:
            stats = mine_repository(config, database)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    if verbose:
        console.print(stats.summary())


if __name__ == "__main__":
    app()
