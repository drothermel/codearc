# Future Extensions

The v0 symbol-history extractor is complete. This document outlines potential next steps.

## Downstream Analysis (Original Vision)

The extracted symbol database enables:

- **Validation** - Check if extracted snippets are valid/runnable Python
- **Dependency analysis** - Identify external deps vs stdlib-only functions
- **Similarity search** - Find similar functions and cluster variants
- **Quality assessment** - Detect redundancy, testability issues, intention mismatches

## Extraction Enhancements

| Feature | Description |
|---------|-------------|
| Nested functions | Currently skipped; could be extracted with parent qualname |
| Module-level constants | Store as separate symbols for cross-reference |
| Name references | Record identifiers used in function bodies (best-effort) |
| Decorators/imports | Populate `extra_json` with structured metadata |
| File-level caching | Hash file content to skip re-parsing unchanged files |

## Additional Libraries

| Library | Use Case |
|---------|----------|
| **ChromaDB** | Vector embeddings for semantic similarity search across versions |
| **Griffe** | Structured API model extraction for API-diff analysis |
| **Jedi** | Static analysis for cross-module reference resolution |
| **tree-sitter** | Fast parsing layer before LibCST for large repos |
| **unidiff** | Parse PR diffs directly from GitHub API |

## GitHub Integration

- **PR-level grouping** - Map commits to PRs via GitHub API/CLI
- **Metadata enrichment** - Store PR titles, labels, review status
- **Remote repos** - Clone and mine repos by URL (not just local paths)

## Performance

- **Parallel processing** - Process multiple files/commits concurrently
- **Incremental updates** - Efficient re-mining when repo has new commits
- **Progress reporting** - Rich progress bars for long-running extractions
