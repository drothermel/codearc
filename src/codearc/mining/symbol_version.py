from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from codearc.models.extracted_symbol import SymbolKind


class SymbolVersion(BaseModel):
    """A versioned symbol tied to a specific commit."""

    repo_id: str = Field(description="Repository identifier")
    commit_hash: str = Field(description="Git commit SHA")
    commit_time: datetime = Field(description="Commit timestamp")
    file_path: str = Field(description="Path to file within repo")
    module: str = Field(description="Python module path (e.g., foo.bar.baz)")
    name: str = Field(description="Simple name of the symbol")
    qualname: str = Field(description="Qualified name")
    kind: SymbolKind = Field(description="Type of symbol")
    code: str = Field(description="Full source code")
    code_hash: str = Field(description="Hash of the code content")
    start_line: int = Field(description="Starting line number")
    end_line: int = Field(description="Ending line number")
    docstring: str | None = Field(default=None)
    extra_json: str | None = Field(default=None, description="Extra metadata as JSON")

    @computed_field
    @property
    def symbol_key(self) -> str:
        """Unique identifier for the symbol across versions."""
        return f"{self.repo_id}:{self.module}:{self.qualname}:{self.kind}"

    @computed_field
    @property
    def version_key(self) -> str:
        """Unique identifier for this specific version."""
        return f"{self.symbol_key}:{self.code_hash}"

    def to_db_tuple(self) -> tuple:
        """Convert to tuple for database insertion."""
        return (
            self.version_key,
            self.symbol_key,
            self.repo_id,
            self.commit_hash,
            self.commit_time,
            self.file_path,
            self.module,
            self.start_line,
            self.end_line,
            self.kind,
            self.qualname,
            self.code,
            self.code_hash,
            self.docstring,
            self.extra_json,
        )
