import hashlib
from datetime import UTC, datetime
from pathlib import Path


def compute_code_hash(code: str) -> str:
    """Compute a deterministic hash of code content."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


def make_absolute(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def get_base_path(package_root: Path | None, repo_root: Path) -> Path:
    if package_root:
        abs_package_root = make_absolute(package_root, repo_root)
        if not abs_package_root.is_dir():
            raise ValueError(f"Package root {abs_package_root} is not a directory")
        return abs_package_root
    if (src_dir := repo_root / "src").is_dir():
        return src_dir
    return repo_root


def convert_file_path_to_module(file_path: Path, base_path: Path) -> str:
    rel_path = file_path.relative_to(base_path)
    module_path = str(rel_path).removesuffix(".py").replace("/", ".").replace("\\", ".")
    if module_path.endswith(".__init__"):
        module_path = module_path.removesuffix(".__init__")
    elif module_path == "__init__":
        # Edge case: just __init__.py at the root
        module_path = ""
    return module_path


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
    path = make_absolute(Path(file_path), repo_root)
    base = get_base_path(package_root, repo_root)
    try:
        module_path = convert_file_path_to_module(path, base)
    except ValueError as e:
        raise ValueError(f"File path {path} is not under base {base}") from e
    return module_path


def safe_decode(content: bytes, encodings: list[str] | None = None) -> str | None:
    """Try to decode bytes using multiple encodings."""
    encodings = encodings or ["utf-8", "cp1252", "latin-1"]
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone.

    For naive datetimes (no tzinfo), assumes the value is already in UTC.
    For aware datetimes, converts to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
