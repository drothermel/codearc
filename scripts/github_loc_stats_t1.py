#!/usr/bin/env python3
"""Aggregate personal GitHub addition/deletion stats by week."""

import csv
import json
import subprocess
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import typer
from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=False)
console = Console()

GITHUB_API = "https://api.github.com"


def github_week_start(value: date) -> date:
    return value - timedelta(days=(value.weekday() + 1) % 7)


class GitHubRepo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str
    private: bool
    fork: bool
    archived: bool
    default_branch: str
    pushed_at: datetime | None = None


class ContributorAuthor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    login: str | None = None


class ContributorWeek(BaseModel):
    model_config = ConfigDict(extra="forbid")

    w: int
    a: int
    d: int
    c: int

    @property
    def week_start(self) -> date:
        return github_week_start(datetime.fromtimestamp(self.w, tz=UTC).date())


class ContributorStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    author: ContributorAuthor | None = None
    total: int = 0
    weeks: list[ContributorWeek] = Field(default_factory=list)


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
    status: str
    additions: int = 0
    deletions: int = 0
    commits: int = 0
    weeks: int = 0
    note: str = ""


class CommitAuthorInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: datetime


class CommitInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    author: CommitAuthorInfo


class CommitStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    additions: int = 0
    deletions: int = 0


class CommitListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str
    commit: CommitInfo


class CommitDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str
    commit: CommitInfo
    stats: CommitStats | None = None


def gh_auth_token() -> str:
    result = subprocess.run(
        ["gh", "auth", "token"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def request_json(
    path: str,
    *,
    token: str,
    query: dict[str, str] | None = None,
) -> tuple[Any, dict[str, str], int]:
    url = f"{GITHUB_API}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    with urlopen(request) as response:
        status = response.status
        headers = dict(response.headers.items())
        payload = response.read().decode("utf-8")
    return json.loads(payload) if payload else None, headers, status


def next_page_path(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' not in part:
            continue
        url_part = part.split(";", maxsplit=1)[0].strip()
        url = url_part.strip("<>")
        parsed = urlparse(url)
        return f"{parsed.path}?{parsed.query}"
    return None


def split_api_path(path: str) -> tuple[str, dict[str, str] | None]:
    parsed = urlparse(path)
    if not parsed.query:
        return parsed.path, None
    return (
        parsed.path,
        {key: values[-1] for key, values in parse_qs(parsed.query).items()},
    )


def get_viewer_login(token: str) -> str:
    payload, _, _ = request_json("/user", token=token)
    return str(payload["login"])


def list_repos(
    token: str,
    *,
    include_forks: bool,
    include_archived: bool,
    limit_repos: int | None,
) -> list[GitHubRepo]:
    repos: list[GitHubRepo] = []
    path = "/user/repos"
    query = {
        "affiliation": "owner,collaborator,organization_member",
        "per_page": "100",
        "sort": "pushed",
        "direction": "desc",
    }

    while path:
        if "?" in path:
            next_path, next_query = split_api_path(path)
            payload, headers, _ = request_json(
                next_path,
                token=token,
                query=next_query,
            )
        else:
            payload, headers, _ = request_json(path, token=token, query=query)

        for raw_repo in payload:
            repo = GitHubRepo(**raw_repo)
            if repo.fork and not include_forks:
                continue
            if repo.archived and not include_archived:
                continue
            repos.append(repo)
            if limit_repos is not None and len(repos) >= limit_repos:
                return repos
        path = next_page_path(headers.get("Link"))

    return repos


def paginated_get(
    path: str,
    *,
    token: str,
    query: dict[str, str],
    limit: int | None = None,
) -> list[Any]:
    rows: list[Any] = []
    while path:
        if "?" in path:
            current_path, current_query = split_api_path(path)
        else:
            current_path = path
            current_query = query
        payload, headers, _ = request_json(
            current_path,
            token=token,
            query=current_query,
        )
        if not payload:
            break
        for row in payload:
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                return rows
        path = next_page_path(headers.get("Link"))
    return rows


def get_contributor_stats(
    token: str,
    repo: GitHubRepo,
    *,
    max_retries: int,
    retry_sleep: float,
) -> list[ContributorStats] | None:
    path = f"/repos/{repo.full_name}/stats/contributors"
    for attempt in range(max_retries + 1):
        try:
            payload, _, status = request_json(path, token=token)
        except HTTPError as exc:
            if exc.code == 202 and attempt < max_retries:
                time.sleep(retry_sleep)
                continue
            if exc.code in {202, 204, 404, 409, 422}:
                return None
            raise
        if status == 202:
            if attempt < max_retries:
                time.sleep(retry_sleep)
                continue
            return None
        if payload is None:
            return None
        return [ContributorStats(**item) for item in payload]
    return None


def get_commit_detail(
    token: str,
    repo: GitHubRepo,
    sha: str,
) -> CommitDetail | None:
    try:
        payload, _, _ = request_json(
            f"/repos/{repo.full_name}/commits/{sha}",
            token=token,
        )
    except HTTPError as exc:
        if exc.code in {404, 409, 422}:
            return None
        raise
    if payload is None:
        return None
    return CommitDetail(**payload)


def aggregate_commit_fallback(
    token: str,
    weekly_totals: dict[date, WeeklyTotal],
    repo: GitHubRepo,
    login: str,
    *,
    max_commits_per_repo: int | None,
) -> RepoResult:
    raw_commits = paginated_get(
        f"/repos/{repo.full_name}/commits",
        token=token,
        query={"author": login, "per_page": "100"},
        limit=max_commits_per_repo,
    )
    commits = [CommitListItem(**raw_commit) for raw_commit in raw_commits]
    additions = 0
    deletions = 0
    commit_count = 0
    active_weeks: set[date] = set()

    for commit in commits:
        detail = get_commit_detail(token, repo, commit.sha)
        if detail is None or detail.stats is None:
            continue
        week_start = github_week_start(detail.commit.author.date.date())
        weekly = weekly_totals.setdefault(
            week_start,
            WeeklyTotal(week_start=week_start),
        )
        weekly.additions += detail.stats.additions
        weekly.deletions += detail.stats.deletions
        weekly.commits += 1
        weekly.repos.add(repo.full_name)
        additions += detail.stats.additions
        deletions += detail.stats.deletions
        commit_count += 1
        active_weeks.add(week_start)

    if commit_count == 0:
        return RepoResult(
            repo=repo.full_name,
            status="no_user_commits",
            note=f"No authored commits found for {login}.",
        )

    return RepoResult(
        repo=repo.full_name,
        status="ok_commit_fallback",
        additions=additions,
        deletions=deletions,
        commits=commit_count,
        weeks=len(active_weeks),
        note="Used per-commit GitHub API because contributor stats were unavailable.",
    )


def find_user_stats(
    contributor_stats: list[ContributorStats],
    login: str,
) -> ContributorStats | None:
    for stats in contributor_stats:
        if stats.author and stats.author.login == login:
            return stats
    return None


def aggregate_repo(
    weekly_totals: dict[date, WeeklyTotal],
    repo: GitHubRepo,
    stats: ContributorStats,
) -> RepoResult:
    additions = 0
    deletions = 0
    commits = 0
    active_weeks = 0
    for week in stats.weeks:
        if week.a == 0 and week.d == 0 and week.c == 0:
            continue
        weekly = weekly_totals.setdefault(
            week.week_start,
            WeeklyTotal(week_start=week.week_start),
        )
        weekly.additions += week.a
        weekly.deletions += week.d
        weekly.commits += week.c
        weekly.repos.add(repo.full_name)
        additions += week.a
        deletions += week.d
        commits += week.c
        active_weeks += 1

    return RepoResult(
        repo=repo.full_name,
        status="ok",
        additions=additions,
        deletions=deletions,
        commits=commits,
        weeks=active_weeks,
    )


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
                "status",
                "additions",
                "deletions",
                "net",
                "commits",
                "weeks",
                "note",
            ],
        )
        writer.writeheader()
        for result in repo_results:
            writer.writerow(
                {
                    "repo": result.repo,
                    "status": result.status,
                    "additions": result.additions,
                    "deletions": result.deletions,
                    "net": result.additions - result.deletions,
                    "commits": result.commits,
                    "weeks": result.weeks,
                    "note": result.note,
                }
            )


def print_summary(
    repo_results: list[RepoResult], weekly_totals: dict[date, WeeklyTotal]
) -> None:
    total_additions = sum(result.additions for result in repo_results)
    total_deletions = sum(result.deletions for result in repo_results)
    total_commits = sum(result.commits for result in repo_results)

    table = Table(title="GitHub contributor stats t1")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Repos scanned", str(len(repo_results)))
    table.add_row(
        "Repos with stats",
        str(sum(r.status in {"ok", "ok_commit_fallback"} for r in repo_results)),
    )
    table.add_row("Active weeks", str(len(weekly_totals)))
    table.add_row("Additions", f"{total_additions:,}")
    table.add_row("Deletions", f"{total_deletions:,}")
    table.add_row("Net", f"{total_additions - total_deletions:,}")
    table.add_row("Commits", f"{total_commits:,}")
    console.print(table)


@app.command()
def main(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory for CSV outputs."),
    ] = Path("github_loc_stats_t1"),
    login: Annotated[
        str | None,
        typer.Option("--login", help="GitHub login to match. Defaults to gh user."),
    ] = None,
    limit_repos: Annotated[
        int | None,
        typer.Option("--limit-repos", min=1, help="Limit repos for a quick test."),
    ] = None,
    include_forks: Annotated[
        bool,
        typer.Option("--include-forks/--exclude-forks"),
    ] = True,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived/--exclude-archived"),
    ] = True,
    max_retries: Annotated[int, typer.Option("--max-retries", min=0)] = 3,
    retry_sleep: Annotated[float, typer.Option("--retry-sleep", min=0)] = 2.0,
    fallback_commits: Annotated[
        bool,
        typer.Option("--fallback-commits/--no-fallback-commits"),
    ] = True,
    max_commits_per_repo: Annotated[
        int | None,
        typer.Option(
            "--max-commits-per-repo",
            min=1,
            help="Optional cap for the slower per-commit fallback.",
        ),
    ] = None,
) -> None:
    """Collect weekly personal additions/deletions from GitHub repo stats."""
    token = gh_auth_token()
    resolved_login = login or get_viewer_login(token)
    output_dir.mkdir(parents=True, exist_ok=True)

    repos = list_repos(
        token,
        include_forks=include_forks,
        include_archived=include_archived,
        limit_repos=limit_repos,
    )

    weekly_totals: dict[date, WeeklyTotal] = {}
    repo_results: list[RepoResult] = []
    for repo in repos:
        console.print(f"Fetching stats for {repo.full_name}")
        contributor_stats = get_contributor_stats(
            token,
            repo,
            max_retries=max_retries,
            retry_sleep=retry_sleep,
        )
        if contributor_stats is None:
            if fallback_commits:
                repo_results.append(
                    aggregate_commit_fallback(
                        token,
                        weekly_totals,
                        repo,
                        resolved_login,
                        max_commits_per_repo=max_commits_per_repo,
                    )
                )
            else:
                repo_results.append(
                    RepoResult(
                        repo=repo.full_name,
                        status="missing",
                        note="GitHub returned no contributor stats.",
                    )
                )
            continue
        user_stats = find_user_stats(contributor_stats, resolved_login)
        if user_stats is None:
            repo_results.append(
                RepoResult(
                    repo=repo.full_name,
                    status="no_user_stats",
                    note=f"No contributor entry for {resolved_login}.",
                )
            )
            continue
        repo_results.append(aggregate_repo(weekly_totals, repo, user_stats))

    write_weekly_csv(output_dir / "weekly_loc.csv", weekly_totals)
    write_repo_csv(output_dir / "repo_totals.csv", repo_results)
    print_summary(repo_results, weekly_totals)
    console.print(f"Wrote CSV outputs to {output_dir}")


if __name__ == "__main__":
    app()
