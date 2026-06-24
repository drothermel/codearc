#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pillow",
#   "pygments",
#   "rich",
#   "typer",
# ]
# ///
"""Export simplification example before/after snippets as syntax PNGs."""

from pathlib import Path
from typing import Annotated

import typer
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import PythonLexer
from rich.console import Console

app = typer.Typer(no_args_is_help=False)
console = Console()

BEFORE_MARKER = "# ===== BEFORE ====="
AFTER_MARKER = "# ===== AFTER ====="


def parse_example(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    if BEFORE_MARKER not in text or AFTER_MARKER not in text:
        raise ValueError(f"{path} is missing before/after markers")

    _, rest = text.split(BEFORE_MARKER, maxsplit=1)
    before, after = rest.split(AFTER_MARKER, maxsplit=1)
    return before.strip() + "\n", after.strip() + "\n"


def example_number(path: Path) -> int:
    prefix = path.name.split("_", maxsplit=1)[0]
    try:
        return int(prefix)
    except ValueError:
        return -1


def parse_only(value: str | None) -> set[int] | None:
    if value is None:
        return None
    selected: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        selected.add(int(part))
    return selected


def selected_examples(examples_dir: Path, only: set[int] | None) -> list[Path]:
    paths = sorted(examples_dir.glob("*.py"))
    if only is None:
        return paths
    return [path for path in paths if example_number(path) in only]


def render_png(
    code: str,
    output_path: Path,
    *,
    style: str,
    font_size: int,
    line_numbers: bool,
) -> None:
    formatter = ImageFormatter(
        image_format="PNG",
        style=style,
        font_name="Menlo",
        font_size=font_size,
        line_numbers=line_numbers,
        line_pad=3,
        image_pad=24,
        line_number_bg="#f6f8fa",
        line_number_fg="#6e7781",
    )
    png_bytes = highlight(code, PythonLexer(), formatter)
    output_path.write_bytes(png_bytes)


@app.command()
def main(
    examples_dir: Annotated[
        Path,
        typer.Option("--examples-dir", help="Directory containing t1 .py examples."),
    ] = Path("scripts/exs"),
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory for generated PNG files."),
    ] = Path("scripts/exs_png"),
    only: Annotated[
        str | None,
        typer.Option("--only", help="Comma-separated example numbers, e.g. 1,6,18."),
    ] = None,
    style: Annotated[str, typer.Option("--style", help="Pygments style name.")] = (
        "default"
    ),
    font_size: Annotated[int, typer.Option("--font-size", min=8, max=48)] = 18,
    line_numbers: Annotated[
        bool,
        typer.Option("--line-numbers/--no-line-numbers"),
    ] = True,
) -> None:
    """Render each example's before and after snippets to separate PNG files."""
    selected = selected_examples(examples_dir, parse_only(only))
    if not selected:
        raise typer.BadParameter(f"No examples matched in {examples_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for path in selected:
        before, after = parse_example(path)
        stem = path.stem
        render_png(
            before,
            output_dir / f"{stem}_before.png",
            style=style,
            font_size=font_size,
            line_numbers=line_numbers,
        )
        render_png(
            after,
            output_dir / f"{stem}_after.png",
            style=style,
            font_size=font_size,
            line_numbers=line_numbers,
        )

    console.print(f"Wrote {len(selected) * 2} PNG files to {output_dir}")


if __name__ == "__main__":
    app()
