#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib",
#   "pydantic",
#   "typer",
# ]
# ///
"""Plot local/GitHub LOC stats over time."""

import csv
from datetime import date
from pathlib import Path
from typing import Annotated

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import typer
from pydantic import BaseModel

app = typer.Typer(no_args_is_help=True)


class MonthlyPoint(BaseModel):
    month: date
    additions: int = 0
    deletions: int = 0
    commits: int = 0

    @property
    def net(self) -> int:
        return self.additions - self.deletions


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def load_monthly(path: Path) -> list[MonthlyPoint]:
    by_month: dict[date, MonthlyPoint] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            month = month_start(date.fromisoformat(row["week_start"]))
            point = by_month.get(month)
            if point is None:
                point = MonthlyPoint(month=month)
                by_month[month] = point
            point.additions += int(row["additions"])
            point.deletions += int(row["deletions"])
            point.commits += int(row["commits"])
    return [by_month[month] for month in sorted(by_month)]


def rolling(values: list[int], window: int = 3) -> list[float]:
    rolled: list[float] = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        chunk = values[start : index + 1]
        rolled.append(sum(chunk) / len(chunk))
    return rolled


def thousands(values: list[int | float]) -> list[float]:
    return [value / 1000 for value in values]


def style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=3))


def add_llm_era(ax, ymax: float) -> None:
    start = date(2023, 1, 1)
    ax.axvspan(start, date.today(), color="#eef2ff", alpha=0.55, zorder=0)
    ax.text(
        start,
        ymax * 0.96 if ymax else 1,
        "LLM coding era",
        color="#4f46e5",
        fontsize=10,
        va="top",
        ha="left",
    )


def plot_combined(
    local: list[MonthlyPoint],
    github: list[MonthlyPoint],
    output: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 7), dpi=180)

    if github:
        months = [point.month for point in github]
        additions = [point.additions for point in github]
        ax.bar(
            months,
            thousands(additions),
            width=24,
            color="#9ca3af",
            alpha=0.35,
            label="GitHub monthly additions, capped",
        )
        ax.plot(
            months,
            thousands(rolling(additions)),
            color="#374151",
            linewidth=2.4,
            label="GitHub 3-month rolling additions",
        )

    if local:
        months = [point.month for point in local]
        additions = [point.additions for point in local]
        ax.plot(
            months,
            thousands(rolling(additions)),
            color="#2563eb",
            linewidth=3,
            label="Local 3-month rolling additions",
        )
        ax.scatter(months, thousands(additions), color="#2563eb", s=14, alpha=0.75)

    all_additions = [point.additions for point in [*local, *github]]
    ymax = max(thousands(all_additions), default=1)
    add_llm_era(ax, ymax)
    style_axes(ax)
    ax.set_title("Personal code additions over time", loc="left", fontsize=18)
    ax.set_ylabel("Additions, thousands of lines")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_local_monthly(local: list[MonthlyPoint], output: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 7), dpi=180)
    months = [point.month for point in local]
    additions = [point.additions for point in local]
    deletions = [point.deletions for point in local]

    ax.bar(
        months,
        thousands(additions),
        width=22,
        color="#2563eb",
        alpha=0.72,
        label="Additions",
    )
    ax.bar(
        months,
        [-value for value in thousands(deletions)],
        width=22,
        color="#ef4444",
        alpha=0.58,
        label="Deletions",
    )
    ax.plot(
        months,
        thousands(rolling(additions)),
        color="#111827",
        linewidth=2.4,
        label="3-month rolling additions",
    )

    style_axes(ax)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_ylabel("Thousands of lines")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_commits(
    local: list[MonthlyPoint],
    github: list[MonthlyPoint],
    output: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 5.5), dpi=180)
    if github:
        months = [point.month for point in github]
        commits = [point.commits for point in github]
        ax.plot(
            months,
            rolling(commits),
            color="#6b7280",
            linewidth=2.3,
            label="GitHub",
        )
    if local:
        months = [point.month for point in local]
        commits = [point.commits for point in local]
        ax.plot(
            months,
            rolling(commits),
            color="#2563eb",
            linewidth=2.8,
            label="Local",
        )

    ymax = max([point.commits for point in [*local, *github]], default=1)
    add_llm_era(ax, ymax)
    style_axes(ax)
    ax.set_title("Authored commits over time", loc="left", fontsize=18)
    ax.set_ylabel("Commits per month, 3-month rolling")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def load_weekly_changed(path: Path, start_date: date) -> tuple[list[date], list[int]]:
    weeks: list[date] = []
    changed: list[int] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            week = date.fromisoformat(row["week_start"])
            if week < start_date:
                continue
            weeks.append(week)
            changed.append(int(row["additions"]) + int(row["deletions"]))
    return weeks, changed


def plot_local_weekly_changed(
    local_csv: Path,
    output: Path,
    *,
    start_date: date,
    rolling_window: int,
) -> None:
    weeks, changed = load_weekly_changed(local_csv, start_date)
    fig, ax = plt.subplots(figsize=(13, 5.8), dpi=180)

    ax.plot(
        weeks,
        thousands(changed),
        color="#93c5fd",
        linewidth=1.2,
        alpha=0.7,
        label="Weekly changed lines",
    )
    ax.plot(
        weeks,
        thousands(rolling(changed, window=rolling_window)),
        color="#1d4ed8",
        linewidth=3.0,
        label=f"{rolling_window}-week rolling average",
    )

    style_axes(ax)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_ylabel("Changed lines, thousands")
    ax.legend(frameon=False, loc="upper left")
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


@app.command()
def main(
    local_csv: Annotated[
        Path,
        typer.Option("--local-csv", help="Local weekly_loc.csv path."),
    ] = Path("local_loc_stats_t1/weekly_loc.csv"),
    github_csv: Annotated[
        Path,
        typer.Option("--github-csv", help="GitHub weekly_loc.csv path."),
    ] = Path("github_loc_stats_t1/weekly_loc.csv"),
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory for plot PNGs."),
    ] = Path("loc_plots_t1"),
    start_date: Annotated[
        str,
        typer.Option("--start-date", help="Start date for focused local weekly plot."),
    ] = "2024-10-01",
    rolling_window: Annotated[
        int,
        typer.Option("--rolling-window", min=1, help="Rolling window in weeks."),
    ] = 4,
    local_monthly_start_date: Annotated[
        str,
        typer.Option(
            "--local-monthly-start-date",
            help="Start date for local monthly churn plot.",
        ),
    ] = "2024-06-01",
) -> None:
    """Create presentation-friendly LOC trend plots."""
    output_dir.mkdir(parents=True, exist_ok=True)
    local = load_monthly(local_csv) if local_csv.exists() else []
    github = load_monthly(github_csv) if github_csv.exists() else []

    plot_combined(local, github, output_dir / "combined_additions_over_time.png")
    if local:
        local_monthly_start = date.fromisoformat(local_monthly_start_date)
        plot_local_monthly(
            [
                point
                for point in local
                if point.month >= month_start(local_monthly_start)
            ],
            output_dir / "local_monthly_churn.png",
        )
        plot_local_weekly_changed(
            local_csv,
            output_dir / "local_weekly_changed_since_late_2024.png",
            start_date=date.fromisoformat(start_date),
            rolling_window=rolling_window,
        )
    plot_commits(local, github, output_dir / "commits_over_time.png")
    print(f"Wrote plots to {output_dir}")


if __name__ == "__main__":
    app()
