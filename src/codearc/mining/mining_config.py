from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field

from codearc.mining.encoding_config import EncodingConfig
from codearc.mining.ignore_patterns import IgnorePatterns


class MiningConfig(BaseModel):
    """Configuration for the mining process."""

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

    @computed_field
    @property
    def effective_repo_id(self) -> str:
        """Repo id derived from explicit repo_id or repo_path."""
        return self.repo_id or self.repo_path.name

    def to_pydriller_kwargs(self) -> dict[str, Any]:
        """Build kwargs dict for PyDriller Repository constructor."""
        kwargs: dict[str, Any] = {
            "only_modifications_with_file_types": [".py"],
        }
        if self.since_commit:
            kwargs["from_commit"] = self.since_commit
        if self.since_date:
            kwargs["since"] = self.since_date
        if self.authors:
            kwargs["only_authors"] = self.authors
        if self.skip_merge_commits:
            kwargs["only_no_merge"] = True
        return kwargs
