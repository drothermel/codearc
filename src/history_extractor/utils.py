import hashlib
from pathlib import Path


def compute_code_hash(code: str) -> str:
    """Compute a deterministic hash of code content."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


def file_path_to_module(
    file_path: str,
    repo_root: Path,
    package_root: Path | None = None,
) -> str:
    """
    Convert a file path to a Python module path.

    Resolution order:
    1. If package_root provided, use it as base
    2. Else if src/ exists in repo, use it as base
    3. Else use repo root as base

    Examples:
        src/foo/bar.py -> foo.bar
        mypackage/utils.py -> mypackage.utils
    """
    path = Path(file_path)

    # If path is relative, make it absolute relative to repo_root
    if not path.is_absolute():
        path = repo_root / path

    # Determine the base path for module calculation
    if package_root is not None:
        base = package_root if package_root.is_absolute() else repo_root / package_root
    elif (repo_root / "src").is_dir():
        base = repo_root / "src"
    else:
        base = repo_root

    # Make path relative to base
    try:
        rel_path = path.relative_to(base)
    except ValueError:
        # Path is not under base, try relative to repo root
        try:
            rel_path = path.relative_to(repo_root)
        except ValueError:
            # Fall back to just the filename
            rel_path = Path(path.name)

    # Convert path to module: remove .py, replace / with .
    module_path = str(rel_path).removesuffix(".py").replace("/", ".").replace("\\", ".")

    # Handle __init__.py -> package name
    if module_path.endswith(".__init__"):
        module_path = module_path.removesuffix(".__init__")
    elif module_path == "__init__":
        # Edge case: just __init__.py at the root
        module_path = ""

    return module_path


def safe_decode(content: bytes, encodings: list[str] | None = None) -> str | None:
    """
    Try to decode bytes using multiple encodings.

    Returns decoded string or None if all encodings fail.
    """
    if encodings is None:
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

    for encoding in encodings:
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    return None
