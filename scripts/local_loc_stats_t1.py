#!/usr/bin/env python3
"""Aggregate local git-authored addition/deletion stats by week."""

import csv
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=False)
console = Console()


class WeeklyTotal(BaseModel):
    week_start: date
    additions: int = 0
    deletions: int = 0
    commits: int = 0
    repos: set[str] = Field(default_factory=set)

    @property
    def net(self) -> int:
        return self.additions - self.deletions


class RepoResult(BaseModel):
    repo: str
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    commits: int = 0
    weeks: int = 0
    matched_authors: set[str] = Field(default_factory=set)
    note: str = ""

    @property
    def net(self) -> int:
        return self.additions - self.deletions


class CommitContext(BaseModel):
    sha: str
    day: date
    author_name: str
    author_email: str
    matches_author: bool

    @property
    def author_label(self) -> str:
        return f"{self.author_name} <{self.author_email}>"


def week_start(day: date) -> date:
    return day - timedelta(days=(day.weekday() + 1) % 7)


def run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def git_config_value(key: str) -> str | None:
    result = subprocess.run(
        ["git", "config", "--global", key],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return value or None


def default_author_matches() -> list[str]:
    values = [
        git_config_value("user.name"),
        git_config_value("user.email"),
        "drothermel",
    ]
    deduped: list[str] = []
    for value in values:
        if value and value.lower() not in {item.lower() for item in deduped}:
            deduped.append(value)
    return deduped


def discover_repos(root: Path) -> list[Path]:
    return sorted(path.parent for path in root.glob("*/.git") if path.is_dir())


def parse_commit_header(line: str, author_matches: list[str]) -> CommitContext:
    _, sha, raw_day, author_name, author_email = line.split("\t", maxsplit=4)
    haystack = f"{author_name}\n{author_email}".lower()
    matches_author = any(match.lower() in haystack for match in author_matches)
    return CommitContext(
        sha=sha,
        day=date.fromisoformat(raw_day),
        author_name=author_name,
        author_email=author_email,
        matches_author=matches_author,
    )


def parse_numstat_line(line: str) -> tuple[int, int] | None:
    parts = line.split("\t", maxsplit=2)
    if len(parts) < 3:
        return None
    additions, deletions = parts[0], parts[1]
    if additions == "-" or deletions == "-":
        return None
    return int(additions), int(deletions)


def aggregate_repo(
    repo: Path,
    author_matches: list[str],
    weekly_totals: dict[date, WeeklyTotal],
    *,
    include_merges: bool,
    all_branches: bool,
) -> RepoResult:
    args = [
        "log",
        "--numstat",
        "--date=short",
        "--format=COMMIT%x09%H%x09%ad%x09%an%x09%ae",
    ]
    if all_branches:
        args.append("--all")
    if not include_merges:
        args.append("--no-merges")

    try:
        output = run_git(repo, args)
    except subprocess.CalledProcessError as exc:
        return RepoResult(
            repo=repo.name,
            path=str(repo),
            status="error",
            note=exc.stderr.strip(),
        )

    result = RepoResult(repo=repo.name, path=str(repo), status="ok")
    active_weeks: set[date] = set()
    current: CommitContext | None = None

    for line in output.splitlines():
        if line.startswith("COMMIT\t"):
            current = parse_commit_header(line, author_matches)
            if not current.matches_author:
                continue

            current_week = week_start(current.day)
            weekly = weekly_totals.setdefault(
                current_week,
                WeeklyTotal(week_start=current_week),
            )
            weekly.commits += 1
            weekly.repos.add(repo.name)
            result.commits += 1
            result.matched_authors.add(current.author_label)
            active_weeks.add(current_week)
            continue

        if current is None or not current.matches_author or not line:
            continue
        parsed = parse_numstat_line(line)
        if parsed is None:
            continue
        additions, deletions = parsed
        current_week = week_start(current.day)
        weekly = weekly_totals.setdefault(
            current_week,
            WeeklyTotal(week_start=current_week),
        )
        weekly.additions += additions
        weekly.deletions += deletions
        result.additions += additions
        result.deletions += deletions

    result.weeks = len(active_weeks)
    if result.commits == 0:
        result.status = "no_matching_commits"
    return result


def write_weekly_csv(path: Path, weekly_totals: dict[date, WeeklyTotal]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "week_start",
                "additions",
                "deletions",
                "net",
                "commits",
                "repo_count",
                "repos",
            ],
        )
        writer.writeheader()
        for week in sorted(weekly_totals):
            total = weekly_totals[week]
            writer.writerow(
                {
                    "week_start": total.week_start.isoformat(),
                    "additions": total.additions,
                    "deletions": total.deletions,
                    "net": total.net,
                    "commits": total.commits,
                    "repo_count": len(total.repos),
                    "repos": ";".join(sorted(total.repos)),
                }
            )


def write_repo_csv(path: Path, repo_results: list[RepoResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "repo",
                "path",
                "status",
                "additions",
                "deletions",
                "net",
                "commits",
                "weeks",
                "matched_authors",
                "note",
            ],
        )
        writer.writeheader()
        for result in repo_results:
            writer.writerow(
                {
                    "repo": result.repo,
                    "path": result.path,
                    "status": result.status,
                    "additions": result.additions,
                    "deletions": result.deletions,
                    "net": result.net,
                    "commits": result.commits,
                    "weeks": result.weeks,
                    "matched_authors": ";".join(sorted(result.matched_authors)),
                    "note": result.note,
                }
            )


def print_summary(
    repo_results: list[RepoResult], weekly_totals: dict[date, WeeklyTotal]
) -> None:
    total_additions = sum(result.additions for result in repo_results)
    total_deletions = sum(result.deletions for result in repo_results)
    total_commits = sum(result.commits for result in repo_results)

    table = Table(title="Local git LOC stats t1")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Repos scanned", str(len(repo_results)))
    table.add_row(
        "Repos with commits",
        str(sum(result.commits > 0 for result in repo_results)),
    )
    table.add_row("Active weeks", str(len(weekly_totals)))
    table.add_row("Additions", f"{total_additions:,}")
    table.add_row("Deletions", f"{total_deletions:,}")
    table.add_row("Net", f"{total_additions - total_deletions:,}")
    table.add_row("Commits", f"{total_commits:,}")
    console.print(table)


@app.command()
def main(
    repos: Annotated[
        list[Path] | None,
        typer.Argument(help="Repos to scan. Defaults to sibling git repos."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory for CSV outputs."),
    ] = Path("local_loc_stats_t1"),
    author_match: Annotated[
        list[str] | None,
        typer.Option(
            "--author-match",
            help="Case-insensitive substring to match author name/email.",
        ),
    ] = None,
    discover_root: Annotated[
        Path,
        typer.Option("--discover-root", help="Root used when repos are omitted."),
    ] = Path(".."),
    include_merges: Annotated[
        bool,
        typer.Option("--include-merges/--no-merges"),
    ] = False,
    all_branches: Annotated[
        bool,
        typer.Option("--all-branches/--current-branch"),
    ] = True,
) -> None:
    """Collect weekly additions/deletions from local git history."""
    author_matches = author_match or default_author_matches()
    repo_paths = repos or discover_repos(discover_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    weekly_totals: dict[date, WeeklyTotal] = {}
    repo_results: list[RepoResult] = []

    console.print(f"Author filters: {', '.join(author_matches)}")
    for repo in repo_paths:
        console.print(f"Scanning {repo}")
        repo_results.append(
            aggregate_repo(
                repo,
                author_matches,
                weekly_totals,
                include_merges=include_merges,
                all_branches=all_branches,
            )
        )

    write_weekly_csv(output_dir / "weekly_loc.csv", weekly_totals)
    write_repo_csv(output_dir / "repo_totals.csv", repo_results)
    print_summary(repo_results, weekly_totals)
    console.print(f"Wrote CSV outputs to {output_dir}")


if __name__ == "__main__":
    app()
