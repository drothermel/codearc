from pydantic import BaseModel, Field


class MiningStats(BaseModel):
    """Statistics tracked during the mining process."""

    commits_processed: int = Field(default=0)
    commits_skipped: int = Field(default=0)
    files_processed: int = Field(default=0)
    files_skipped: int = Field(default=0)
    symbols_extracted: int = Field(default=0)
    symbols_deduplicated: int = Field(default=0)
    parse_errors: int = Field(default=0)
    encoding_errors: int = Field(default=0)

    def increment_commits_processed(self) -> None:
        self.commits_processed += 1

    def increment_commits_skipped(self) -> None:
        self.commits_skipped += 1

    def increment_files_processed(self) -> None:
        self.files_processed += 1

    def increment_files_skipped(self) -> None:
        self.files_skipped += 1

    def add_symbols(self, count: int) -> None:
        if count < 0:
            raise ValueError(f"count must be non-negative, got {count}")
        self.symbols_extracted += count

    def add_deduplicated(self, count: int) -> None:
        if count < 0:
            raise ValueError(f"count must be non-negative, got {count}")
        self.symbols_deduplicated += count

    def increment_parse_errors(self) -> None:
        self.parse_errors += 1

    def increment_encoding_errors(self) -> None:
        self.encoding_errors += 1

    def summary(self) -> str:
        """Return a human-readable summary."""
        return (
            f"Commits: {self.commits_processed} processed, "
            f"{self.commits_skipped} skipped | "
            f"Files: {self.files_processed} processed, "
            f"{self.files_skipped} skipped | "
            f"Symbols: {self.symbols_extracted} extracted, "
            f"{self.symbols_deduplicated} deduped | "
            f"Errors: {self.parse_errors} parse, "
            f"{self.encoding_errors} encoding"
        )
