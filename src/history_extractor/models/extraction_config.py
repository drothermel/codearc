from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from history_extractor.models.encoding_config import EncodingConfig
from history_extractor.models.ignore_patterns import IgnorePatterns


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

    @computed_field
    @property
    def effective_repo_id(self) -> str:
        """Repo id derived from explicit repo_id or repo_path."""
        return self.repo_id or self.repo_path.name
