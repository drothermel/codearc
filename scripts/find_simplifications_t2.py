#!/usr/bin/env python3
"""Rank slide-sized simplification examples from codearc DuckDB outputs."""

import ast
import io
import re
import tokenize
from collections.abc import Iterable
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

NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)

ANCHOR_NODE_LIMIT = 300


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


class SignatureInfo(BaseModel):
    args: tuple[str, ...] = ()
    is_async: bool = False
    decorators: tuple[str, ...] = ()


class CodeMetrics(BaseModel):
    lines: int
    chars: int
    docstring_chars: int
    comment_lines: int
    comment_chars: int
    inline_comment_count: int
    try_count: int
    except_count: int
    branch_count: int
    defensive_count: int
    max_nesting: int
    return_count: int
    signature: SignatureInfo
    anchors: set[str]
    parse_ok: bool


class Candidate(BaseModel):
    score: float
    old: SymbolRow
    new: SymbolRow
    old_metrics: CodeMetrics
    new_metrics: CodeMetrics
    line_reduction: float
    char_reduction: float
    docstring_reduction: float
    comment_reduction: float
    branch_delta: int
    nesting_delta: int
    try_delta: int
    except_delta: int
    defensive_delta: int
    signature_same: bool
    anchor_similarity: float


def count_nodes(
    tree: ast.AST,
    node_type: type[ast.AST] | tuple[type[ast.AST], ...],
) -> int:
    return sum(isinstance(node, node_type) for node in ast.walk(tree))


def count_defensive_patterns(code: str) -> int:
    return sum(len(pattern.findall(code)) for pattern in DEFENSIVE_PATTERNS)


def count_comment_metrics(code: str) -> tuple[int, int, int]:
    comment_lines: set[int] = set()
    comment_chars = 0
    inline_comment_count = 0
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            comment_lines.add(token.start[0])
            comment_chars += len(token.string)
            prefix = token.line[: token.start[1]]
            if prefix.strip():
                inline_comment_count += 1
    except tokenize.TokenError:
        comment_lines = set(re.findall(r"^\s*#", code, flags=re.MULTILINE))
        comment_chars = sum(
            len(line.strip())
            for line in code.splitlines()
            if line.lstrip().startswith("#")
        )
    return len(comment_lines), comment_chars, inline_comment_count


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        if parent is None:
            return node.attr
        return f"{parent}.{node.attr}"
    return None


def arg_names(args: ast.arguments) -> tuple[str, ...]:
    names = [arg.arg for arg in args.posonlyargs]
    names.extend(arg.arg for arg in args.args)
    if args.vararg is not None:
        names.append(f"*{args.vararg.arg}")
    names.extend(arg.arg for arg in args.kwonlyargs)
    if args.kwarg is not None:
        names.append(f"**{args.kwarg.arg}")
    return tuple(names)


def signature_for(tree: ast.AST) -> SignatureInfo:
    first = next(
        (
            node
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        ),
        None,
    )
    if isinstance(first, ast.FunctionDef | ast.AsyncFunctionDef):
        decorators = tuple(
            name
            for decorator in first.decorator_list
            if (name := dotted_name(decorator)) is not None
        )
        return SignatureInfo(
            args=arg_names(first.args),
            is_async=isinstance(first, ast.AsyncFunctionDef),
            decorators=decorators,
        )
    return SignatureInfo()


def semantic_anchors(tree: ast.AST) -> set[str]:
    anchors: set[str] = set()
    for index, node in enumerate(ast.walk(tree)):
        if index > ANCHOR_NODE_LIMIT:
            break
        if isinstance(node, ast.Call):
            if name := dotted_name(node.func):
                anchors.add(f"call:{name}")
        elif isinstance(node, ast.Attribute):
            if name := dotted_name(node):
                anchors.add(f"attr:{name}")
        elif isinstance(node, ast.Name) and not node.id.startswith("_"):
            anchors.add(f"name:{node.id}")
        elif isinstance(node, ast.Return):
            anchors.add(f"return:{type(node.value).__name__ if node.value else 'None'}")
    return anchors


def max_nesting_depth(tree: ast.AST) -> int:
    def visit(node: ast.AST, depth: int) -> int:
        next_depth = depth + 1 if isinstance(node, NESTING_NODES) else depth
        child_depths = (
            visit(child, next_depth) for child in ast.iter_child_nodes(node)
        )
        return max([next_depth, *child_depths])

    return visit(tree, 0)


def fallback_count(pattern: str, code: str) -> int:
    return len(re.findall(pattern, code))


def metric_for(code: str, docstring: str | None) -> CodeMetrics:
    lines = len(code.splitlines())
    chars = len(code)
    comment_lines, comment_chars, inline_comment_count = count_comment_metrics(code)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        try_count = fallback_count(r"\btry\s*:", code)
        except_count = fallback_count(r"\bexcept\b", code)
        branch_count = fallback_count(r"\b(if|for|while|with|match)\b", code)
        max_nesting = 0
        return_count = fallback_count(r"\breturn\b", code)
        signature = SignatureInfo()
        anchors: set[str] = set()
        parse_ok = False
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
        max_nesting = max_nesting_depth(tree)
        return_count = count_nodes(tree, ast.Return)
        signature = signature_for(tree)
        anchors = semantic_anchors(tree)
        parse_ok = True

    return CodeMetrics(
        lines=lines,
        chars=chars,
        docstring_chars=len(docstring or ""),
        comment_lines=comment_lines,
        comment_chars=comment_chars,
        inline_comment_count=inline_comment_count,
        try_count=try_count,
        except_count=except_count,
        branch_count=branch_count,
        defensive_count=count_defensive_patterns(code),
        max_nesting=max_nesting,
        return_count=return_count,
        signature=signature,
        anchors=anchors,
        parse_ok=parse_ok,
    )


def reduction(old_value: int, new_value: int) -> float:
    if old_value <= 0:
        return 0.0
    return (old_value - new_value) / old_value


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


def score_pair(old: SymbolRow, new: SymbolRow) -> Candidate:
    old_metrics = metric_for(old.code, old.docstring)
    new_metrics = metric_for(new.code, new.docstring)
    line_reduction = reduction(old_metrics.lines, new_metrics.lines)
    char_reduction = reduction(old_metrics.chars, new_metrics.chars)
    docstring_reduction = reduction(
        old_metrics.docstring_chars,
        new_metrics.docstring_chars,
    )
    comment_reduction = reduction(old_metrics.comment_lines, new_metrics.comment_lines)
    branch_delta = old_metrics.branch_count - new_metrics.branch_count
    nesting_delta = old_metrics.max_nesting - new_metrics.max_nesting
    try_delta = old_metrics.try_count - new_metrics.try_count
    except_delta = old_metrics.except_count - new_metrics.except_count
    defensive_delta = old_metrics.defensive_count - new_metrics.defensive_count
    signature_same = old_metrics.signature == new_metrics.signature
    anchor_similarity = jaccard(old_metrics.anchors, new_metrics.anchors)
    try_except_removed = (
        old_metrics.try_count > 0
        and old_metrics.except_count > 0
        and new_metrics.try_count == 0
        and new_metrics.except_count == 0
    )
    moderate_size_bonus = (
        18 <= old_metrics.lines <= 80
        and 6 <= new_metrics.lines <= 35
        and 0.20 <= line_reduction <= 0.70
    )

    score = (
        2.0 * line_reduction
        + 1.0 * char_reduction
        + 3.0 * docstring_reduction
        + 3.0 * comment_reduction
        + (4.0 if try_except_removed else 0.0)
        + 2.0 * max(0, nesting_delta)
        + 1.25 * max(0, branch_delta)
        + 1.25 * max(0, defensive_delta)
        + (2.0 if signature_same else -3.0)
        + 2.0 * anchor_similarity
        + (2.0 if moderate_size_bonus else 0.0)
    )
    if old_metrics.lines > 90:
        score -= min(4.0, (old_metrics.lines - 90) / 20)
    if new_metrics.lines > 45:
        score -= min(3.0, (new_metrics.lines - 45) / 15)
    if anchor_similarity < 0.40:
        score -= 4.0

    return Candidate(
        score=score,
        old=old,
        new=new,
        old_metrics=old_metrics,
        new_metrics=new_metrics,
        line_reduction=line_reduction,
        char_reduction=char_reduction,
        docstring_reduction=docstring_reduction,
        comment_reduction=comment_reduction,
        branch_delta=branch_delta,
        nesting_delta=nesting_delta,
        try_delta=try_delta,
        except_delta=except_delta,
        defensive_delta=defensive_delta,
        signature_same=signature_same,
        anchor_similarity=anchor_similarity,
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
    max_old_lines: int,
    min_new_lines: int,
    max_new_lines: int,
    min_line_reduction: float,
    max_line_reduction: float,
    min_old_docstring_chars: int,
    max_new_docstring_chars: int,
    min_old_comment_lines: int,
    max_new_comment_lines: int,
    min_anchor_similarity: float,
    min_score: float,
    require_try_except_removed: bool,
    require_signature_same: bool,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for db_path in db_paths:
        rows = load_rows(db_path, include_classes=include_classes)
        for old, new in iter_adjacent_versions(rows):
            candidate = score_pair(old, new)
            old_metrics = candidate.old_metrics
            new_metrics = candidate.new_metrics
            if not old_metrics.parse_ok or not new_metrics.parse_ok:
                continue
            if not min_old_lines <= old_metrics.lines <= max_old_lines:
                continue
            if not min_new_lines <= new_metrics.lines <= max_new_lines:
                continue
            if not min_line_reduction <= candidate.line_reduction <= max_line_reduction:
                continue
            if old_metrics.docstring_chars < min_old_docstring_chars:
                continue
            if new_metrics.docstring_chars > max_new_docstring_chars:
                continue
            if old_metrics.comment_lines < min_old_comment_lines:
                continue
            if new_metrics.comment_lines > max_new_comment_lines:
                continue
            if require_try_except_removed and (
                old_metrics.try_count < 1
                or old_metrics.except_count < 1
                or new_metrics.try_count != 0
                or new_metrics.except_count != 0
            ):
                continue
            if require_signature_same and not candidate.signature_same:
                continue
            if candidate.anchor_similarity < min_anchor_similarity:
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
        f"docstring {old.docstring_chars}->{new.docstring_chars}, "
        f"comments {old.comment_lines}->{new.comment_lines}, "
        f"try/except {old.try_count}/{old.except_count}->"
        f"{new.try_count}/{new.except_count}, "
        f"nesting {old.max_nesting}->{new.max_nesting}, "
        f"branches {old.branch_count}->{new.branch_count}, "
        f"anchors {candidate.anchor_similarity:.0%}, "
        f"signature {'same' if candidate.signature_same else 'changed'}"
    )


def render_markdown(candidates: list[Candidate], max_code_lines: int) -> str:
    parts = [
        "# Simplification Candidates t2",
        "",
        (
            "Heuristic: adjacent versions of the same symbol that are moderate "
            "length, remove comments/docstrings/try-except/nesting, and retain "
            "similar AST anchor names."
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
            f"# Simplification candidate t2 #{index:03d}",
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
        path = examples_dir / f"{index:03d}_t2_{repo_slug}_{symbol_slug}.py"
        path.write_text(render_example_py(candidate, index), encoding="utf-8")


def print_table(candidates: list[Candidate]) -> None:
    table = Table(title="Top t2 simplification candidates")
    table.add_column("Score", justify="right")
    table.add_column("Repo")
    table.add_column("Symbol")
    table.add_column("Lines", justify="right")
    table.add_column("Signals")

    for candidate in candidates:
        old = candidate.old_metrics
        new = candidate.new_metrics
        signals = [
            f"docs {old.docstring_chars}->{new.docstring_chars}",
            f"comments {old.comment_lines}->{new.comment_lines}",
            f"try/except {old.try_count}/{old.except_count}->"
            f"{new.try_count}/{new.except_count}",
            f"nest {old.max_nesting}->{new.max_nesting}",
            f"anchors {candidate.anchor_similarity:.0%}",
        ]
        table.add_row(
            f"{candidate.score:.2f}",
            candidate.old.repo_id,
            candidate.old.qualname,
            f"{old.lines}->{new.lines}",
            ", ".join(signals),
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
    ] = Path("simplification_candidates_t2.md"),
    limit: Annotated[int, typer.Option("--limit", "-n", min=1)] = 50,
    min_old_lines: Annotated[int, typer.Option("--min-old-lines", min=1)] = 18,
    max_old_lines: Annotated[int, typer.Option("--max-old-lines", min=1)] = 80,
    min_new_lines: Annotated[int, typer.Option("--min-new-lines", min=1)] = 6,
    max_new_lines: Annotated[int, typer.Option("--max-new-lines", min=1)] = 35,
    min_line_reduction: Annotated[
        float,
        typer.Option("--min-line-reduction", min=0.01, max=0.99),
    ] = 0.20,
    max_line_reduction: Annotated[
        float,
        typer.Option("--max-line-reduction", min=0.01, max=0.99),
    ] = 0.70,
    min_old_docstring_chars: Annotated[
        int,
        typer.Option("--min-old-docstring-chars", min=0),
    ] = 40,
    max_new_docstring_chars: Annotated[
        int,
        typer.Option("--max-new-docstring-chars", min=0),
    ] = 80,
    min_old_comment_lines: Annotated[
        int,
        typer.Option("--min-old-comment-lines", min=0),
    ] = 1,
    max_new_comment_lines: Annotated[
        int,
        typer.Option("--max-new-comment-lines", min=0),
    ] = 2,
    min_anchor_similarity: Annotated[
        float,
        typer.Option("--min-anchor-similarity", min=0.0, max=1.0),
    ] = 0.25,
    min_score: Annotated[float, typer.Option("--min-score")] = 5.0,
    max_code_lines: Annotated[int, typer.Option("--max-code-lines", min=1)] = 90,
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
    require_try_except_removed: Annotated[
        bool,
        typer.Option(
            "--require-try-except-removed/--allow-partial-try-except",
            help=(
                "Require old versions to have try/except and new versions to "
                "remove it."
            ),
        ),
    ] = False,
    require_signature_same: Annotated[
        bool,
        typer.Option(
            "--require-signature-same/--allow-signature-change",
            help="Require the function signature to remain unchanged.",
        ),
    ] = True,
) -> None:
    """Find slide-sized before/after simplification examples."""
    if min_old_lines > max_old_lines:
        raise typer.BadParameter("--min-old-lines must be <= --max-old-lines")
    if min_new_lines > max_new_lines:
        raise typer.BadParameter("--min-new-lines must be <= --max-new-lines")
    if min_line_reduction > max_line_reduction:
        raise typer.BadParameter(
            "--min-line-reduction must be <= --max-line-reduction"
        )

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
        max_old_lines=max_old_lines,
        min_new_lines=min_new_lines,
        max_new_lines=max_new_lines,
        min_line_reduction=min_line_reduction,
        max_line_reduction=max_line_reduction,
        min_old_docstring_chars=min_old_docstring_chars,
        max_new_docstring_chars=max_new_docstring_chars,
        min_old_comment_lines=min_old_comment_lines,
        max_new_comment_lines=max_new_comment_lines,
        min_anchor_similarity=min_anchor_similarity,
        min_score=min_score,
        require_try_except_removed=require_try_except_removed,
        require_signature_same=require_signature_same,
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
