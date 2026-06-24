#!/usr/bin/env python3
"""Rank likely simplification examples from codearc DuckDB outputs."""

import ast
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated

import duckdb
import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=False)
console = Console()

DEFENSIVE_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"\bisinstance\s*\(",
        r"\bhasattr\s*\(",
        r"\bgetattr\s*\(",
        r"\bis\s+None\b",
        r"\bis\s+not\s+None\b",
        r"\bassert\b",
        r"\braise\s+(ValueError|RuntimeError|TypeError|KeyError|ImportError)\b",
    ]
]


class SymbolRow(BaseModel):
    db_name: str
    repo_id: str
    symbol_key: str
    commit_hash: str
    commit_time: datetime
    file_path: str
    module: str
    kind: str
    qualname: str
    code: str
    docstring: str | None


class CodeMetrics(BaseModel):
    lines: int
    chars: int
    docstring_chars: int
    try_count: int
    except_count: int
    branch_count: int
    defensive_count: int


class Candidate(BaseModel):
    score: float
    old: SymbolRow
    new: SymbolRow
    old_metrics: CodeMetrics
    new_metrics: CodeMetrics
    line_reduction: float
    char_reduction: float
    branch_delta: int
    try_delta: int
    except_delta: int
    defensive_delta: int
    docstring_removed: bool


def count_nodes(
    tree: ast.AST,
    node_type: type[ast.AST] | tuple[type[ast.AST], ...],
) -> int:
    return sum(isinstance(node, node_type) for node in ast.walk(tree))


def count_defensive_patterns(code: str) -> int:
    return sum(len(pattern.findall(code)) for pattern in DEFENSIVE_PATTERNS)


def metric_for(code: str, docstring: str | None) -> CodeMetrics:
    lines = len(code.splitlines())
    chars = len(code)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        try_count = len(re.findall(r"\btry\s*:", code))
        except_count = len(re.findall(r"\bexcept\b", code))
        branch_count = len(re.findall(r"\b(if|for|while|with|match)\b", code))
    else:
        try_count = count_nodes(tree, ast.Try)
        except_count = sum(
            len(node.handlers) for node in ast.walk(tree) if isinstance(node, ast.Try)
        )
        branch_count = count_nodes(
            tree,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.With,
                ast.AsyncWith,
                ast.Match,
            ),
        )

    return CodeMetrics(
        lines=lines,
        chars=chars,
        docstring_chars=len(docstring or ""),
        try_count=try_count,
        except_count=except_count,
        branch_count=branch_count,
        defensive_count=count_defensive_patterns(code),
    )


def reduction(old_value: int, new_value: int) -> float:
    if old_value <= 0:
        return 0.0
    return (old_value - new_value) / old_value


def score_pair(old: SymbolRow, new: SymbolRow) -> Candidate:
    old_metrics = metric_for(old.code, old.docstring)
    new_metrics = metric_for(new.code, new.docstring)
    line_reduction = reduction(old_metrics.lines, new_metrics.lines)
    char_reduction = reduction(old_metrics.chars, new_metrics.chars)
    branch_delta = old_metrics.branch_count - new_metrics.branch_count
    try_delta = old_metrics.try_count - new_metrics.try_count
    except_delta = old_metrics.except_count - new_metrics.except_count
    defensive_delta = old_metrics.defensive_count - new_metrics.defensive_count
    docstring_removed = bool(old.docstring) and not new.docstring

    score = (
        8.0 * line_reduction
        + 4.0 * char_reduction
        + 2.0 * max(0, try_delta)
        + 2.0 * max(0, except_delta)
        + 1.25 * max(0, defensive_delta)
        + 0.75 * max(0, branch_delta)
        + (1.5 if docstring_removed else 0.0)
    )
    if old_metrics.lines >= 30 and new_metrics.lines <= 12:
        score += 1.0

    return Candidate(
        score=score,
        old=old,
        new=new,
        old_metrics=old_metrics,
        new_metrics=new_metrics,
        line_reduction=line_reduction,
        char_reduction=char_reduction,
        branch_delta=branch_delta,
        try_delta=try_delta,
        except_delta=except_delta,
        defensive_delta=defensive_delta,
        docstring_removed=docstring_removed,
    )


def default_db_paths() -> list[Path]:
    return sorted(Path("mined_dbs").glob("*.duckdb"))


def load_rows(db_path: Path, include_classes: bool) -> list[SymbolRow]:
    kind_filter = "" if include_classes else "where kind = 'function'"
    sql = f"""
        select
            repo_id,
            symbol_key,
            commit_hash,
            commit_time,
            file_path,
            module,
            kind,
            qualname,
            code,
            docstring
        from symbol_versions
        {kind_filter}
        order by symbol_key, commit_time, commit_hash, version_key
    """
    with duckdb.connect(str(db_path), read_only=True) as conn:
        rows = conn.execute(sql).fetchall()

    return [
        SymbolRow(
            db_name=db_path.name,
            repo_id=row[0],
            symbol_key=row[1],
            commit_hash=row[2],
            commit_time=row[3],
            file_path=row[4],
            module=row[5],
            kind=row[6],
            qualname=row[7],
            code=row[8],
            docstring=row[9],
        )
        for row in rows
    ]


def iter_adjacent_versions(rows: list[SymbolRow]):
    previous: SymbolRow | None = None
    for row in rows:
        if previous and previous.symbol_key == row.symbol_key:
            yield previous, row
        previous = row


def find_candidates(
    db_paths: list[Path],
    *,
    include_classes: bool,
    min_old_lines: int,
    max_new_line_ratio: float,
    min_score: float,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for db_path in db_paths:
        rows = load_rows(db_path, include_classes=include_classes)
        for old, new in iter_adjacent_versions(rows):
            candidate = score_pair(old, new)
            if candidate.old_metrics.lines < min_old_lines:
                continue
            if candidate.new_metrics.lines >= candidate.old_metrics.lines:
                continue
            max_new_lines = candidate.old_metrics.lines * max_new_line_ratio
            if candidate.new_metrics.lines > max_new_lines:
                continue
            if candidate.score < min_score:
                continue
            candidates.append(candidate)
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def short_hash(commit_hash: str) -> str:
    return commit_hash[:8]


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return slug[:80] or "candidate"


def clip_code(code: str, max_lines: int) -> str:
    lines = code.splitlines()
    if len(lines) <= max_lines:
        return code
    clipped = "\n".join(lines[:max_lines])
    return f"{clipped}\n# ... clipped {len(lines) - max_lines} lines ..."


def candidate_summary(candidate: Candidate) -> str:
    old = candidate.old_metrics
    new = candidate.new_metrics
    return (
        f"score={candidate.score:.2f}, "
        f"lines {old.lines}->{new.lines} ({candidate.line_reduction:.0%}), "
        f"chars {old.chars}->{new.chars} ({candidate.char_reduction:.0%}), "
        f"try {old.try_count}->{new.try_count}, "
        f"except {old.except_count}->{new.except_count}, "
        f"branches {old.branch_count}->{new.branch_count}, "
        f"defensive {old.defensive_count}->{new.defensive_count}"
    )


def render_markdown(candidates: list[Candidate], max_code_lines: int) -> str:
    parts = [
        "# Simplification Candidates t1",
        "",
        (
            "Heuristic: adjacent versions of the same symbol where the later "
            "version is shorter and loses verbosity signals."
        ),
        "",
    ]
    for index, candidate in enumerate(candidates, start=1):
        old = candidate.old
        new = candidate.new
        parts.extend(
            [
                f"## {index}. `{old.repo_id}:{old.module}.{old.qualname}`",
                "",
                candidate_summary(candidate),
                "",
                f"- DB: `{old.db_name}`",
                f"- File: `{old.file_path}`",
                f"- Before: `{short_hash(old.commit_hash)}` at `{old.commit_time}`",
                f"- After: `{short_hash(new.commit_hash)}` at `{new.commit_time}`",
                (
                    f"- Git helper: `git -C ../{old.repo_id} show "
                    f"{short_hash(new.commit_hash)} -- {old.file_path}`"
                ),
                "",
                "Before:",
                "",
                "```python",
                clip_code(old.code, max_code_lines),
                "```",
                "",
                "After:",
                "",
                "```python",
                clip_code(new.code, max_code_lines),
                "```",
                "",
            ]
        )
    return "\n".join(parts)


def render_example_py(candidate: Candidate, index: int) -> str:
    old = candidate.old
    new = candidate.new
    return "\n".join(
        [
            f"# Simplification candidate t1 #{index:03d}",
            f"# Symbol: {old.repo_id}:{old.module}.{old.qualname}",
            f"# File: {old.file_path}",
            f"# DB: {old.db_name}",
            f"# Before: {short_hash(old.commit_hash)} at {old.commit_time}",
            f"# After: {short_hash(new.commit_hash)} at {new.commit_time}",
            f"# Summary: {candidate_summary(candidate)}",
            (
                f"# Git helper: git -C ../{old.repo_id} show "
                f"{short_hash(new.commit_hash)} -- {old.file_path}"
            ),
            "",
            "# ===== BEFORE =====",
            "",
            old.code.strip(),
            "",
            "",
            "# ===== AFTER =====",
            "",
            new.code.strip(),
            "",
        ]
    )


def export_example_files(candidates: list[Candidate], examples_dir: Path) -> None:
    examples_dir.mkdir(parents=True, exist_ok=True)
    for index, candidate in enumerate(candidates, start=1):
        repo_slug = slugify(candidate.old.repo_id)
        symbol_slug = slugify(candidate.old.qualname)
        path = examples_dir / f"{index:03d}_t1_{repo_slug}_{symbol_slug}.py"
        path.write_text(render_example_py(candidate, index), encoding="utf-8")


def print_table(candidates: list[Candidate]) -> None:
    table = Table(title="Top simplification candidates")
    table.add_column("Score", justify="right")
    table.add_column("Repo")
    table.add_column("Symbol")
    table.add_column("Lines", justify="right")
    table.add_column("Signals")

    for candidate in candidates:
        signals = []
        if candidate.try_delta > 0 or candidate.except_delta > 0:
            signals.append(
                f"try/except -{candidate.try_delta}/{candidate.except_delta}"
            )
        if candidate.defensive_delta > 0:
            signals.append(f"defensive -{candidate.defensive_delta}")
        if candidate.branch_delta > 0:
            signals.append(f"branches -{candidate.branch_delta}")
        if candidate.docstring_removed:
            signals.append("docstring removed")
        table.add_row(
            f"{candidate.score:.2f}",
            candidate.old.repo_id,
            candidate.old.qualname,
            f"{candidate.old_metrics.lines}->{candidate.new_metrics.lines}",
            ", ".join(signals) or "size reduction",
        )

    console.print(table)


@app.command()
def main(
    db_paths: Annotated[
        list[Path] | None,
        typer.Argument(help="DuckDB files to scan. Defaults to mined_dbs/*.duckdb."),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Markdown report path."),
    ] = Path("simplification_candidates_t1.md"),
    limit: Annotated[int, typer.Option("--limit", "-n", min=1)] = 50,
    min_old_lines: Annotated[int, typer.Option("--min-old-lines", min=1)] = 12,
    max_new_line_ratio: Annotated[
        float,
        typer.Option("--max-new-line-ratio", min=0.01, max=0.99),
    ] = 0.70,
    min_score: Annotated[float, typer.Option("--min-score")] = 2.5,
    max_code_lines: Annotated[int, typer.Option("--max-code-lines", min=1)] = 80,
    examples_dir: Annotated[
        Path | None,
        typer.Option(
            "--examples-dir",
            help="Optional directory for full before/after .py review files.",
        ),
    ] = None,
    include_classes: Annotated[
        bool,
        typer.Option(
            "--include-classes",
            help="Include class definitions as candidates.",
        ),
    ] = False,
) -> None:
    """Find likely before/after simplification examples."""
    paths = db_paths or default_db_paths()
    if not paths:
        raise typer.BadParameter(
            "No DB paths provided and mined_dbs/*.duckdb is empty."
        )

    missing_paths = [path for path in paths if not path.exists()]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise typer.BadParameter(f"Missing DB path(s): {missing}")

    candidates = find_candidates(
        paths,
        include_classes=include_classes,
        min_old_lines=min_old_lines,
        max_new_line_ratio=max_new_line_ratio,
        min_score=min_score,
    )[:limit]

    output.write_text(render_markdown(candidates, max_code_lines), encoding="utf-8")
    if examples_dir is not None:
        export_example_files(candidates, examples_dir)
    print_table(candidates[: min(limit, 20)])
    console.print(f"\nWrote {len(candidates)} candidates to {output}")
    if examples_dir is not None:
        console.print(f"Wrote {len(candidates)} example files to {examples_dir}")


if __name__ == "__main__":
    app()
