from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class IgnorePatterns(BaseModel):
    """Glob patterns for files/directories to skip during extraction."""

    patterns: list[str] = Field(
        default=[
            "**/venv/**",
            "**/.venv/**",
            ".venv/**",
            "venv/**",
            "**/site-packages/**",
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/.git/**",
            ".git/**",
            "*_pb2.py",
            "*_pb2_grpc.py",
            "**/.tox/**",
            "**/.nox/**",
            "**/build/**",
            "**/dist/**",
            "**/*.egg-info/**",
        ]
    )

    def matches(self, path: str) -> bool:
        """Check if path matches any ignore pattern."""
        from fnmatch import fnmatch

        return any(fnmatch(path, pattern) for pattern in self.patterns)


class EncodingConfig(BaseModel):
    """Encoding fallbacks for reading source files."""

    encodings: list[str] = Field(default=["utf-8", "latin-1", "cp1252", "iso-8859-1"])


class ExtractionConfig(BaseModel):
    """Configuration for the extraction process."""

    repo_path: Path = Field(description="Path to the git repository")
    db_path: Path = Field(description="Path to the output DuckDB database")
    repo_id: str | None = Field(
        default=None,
        description="Identifier for the repo (defaults to repo directory name)",
    )
    package_root: Path | None = Field(
        default=None,
        description="Root path for module name calculation (e.g., src/)",
    )
    since_commit: str | None = Field(
        default=None,
        description="Resume extraction from this commit hash",
    )
    since_date: datetime | None = Field(
        default=None,
        description="Only process commits after this date",
    )
    authors: list[str] | None = Field(
        default=None,
        description="Only process commits by these authors",
    )
    skip_merge_commits: bool = Field(
        default=True,
        description="Skip merge commits during extraction",
    )
    ignore_patterns: IgnorePatterns = Field(default_factory=IgnorePatterns)
    encoding_config: EncodingConfig = Field(default_factory=EncodingConfig)

    def get_repo_id(self) -> str:
        """Return repo_id or derive from repo_path."""
        return self.repo_id or self.repo_path.name
