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
        self.symbols_extracted += count

    def add_deduplicated(self, count: int) -> None:
        self.symbols_deduplicated += count

    def increment_parse_errors(self) -> None:
        self.parse_errors += 1

    def increment_encoding_errors(self) -> None:
        self.encoding_errors += 1

    def summary(self) -> str:
        """Return a human-readable summary."""
        c = self.commits_processed
        s = self.commits_skipped
        f = self.files_processed
        fs = self.files_skipped
        sym = self.symbols_extracted
        dup = self.symbols_deduplicated
        return (
            f"Commits: {c} processed, {s} skipped | "
            f"Files: {f} processed, {fs} skipped\n"
            f"Symbols: {sym} extracted, {dup} deduped | "
            f"Errors: {self.parse_errors} parse, {self.encoding_errors} encoding"
        )
