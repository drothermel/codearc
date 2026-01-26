Here’s a prompt you can paste directly into a strong coding agent.

---

## Prompt for coding agent: v0 Python symbol-history extractor (Git + DuckDB)

You are a senior engineer building a v0 pipeline that mines a Python GitHub repo’s history and produces a **database of all distinct versions of every function/class/method** that ever existed in the repo.

### Context / ultimate goal (why we’re doing this)

The long-term aim is to support downstream filtering and analysis on extracted definitions, e.g.:

* Validate whether extracted snippets are valid Python / runnable
* Identify external deps vs stdlib-only
* Find similar functions / variants
* Assess testability / detect redundancy / intention mismatches
  **You are NOT implementing these downstream filters now**; design the v0 so they can be added cleanly later.

### v0 objective (what to ship)

Implement a v0 that:

1. Walks a repo’s history (initially commit-level; PR grouping can be layered on later).
2. For each commit, processes changed Python files and extracts:

   * functions (top-level + methods; nested optional but nice)
   * classes
   * optionally module-level constants (store later linkage; this can be minimal in v0)
3. Deduplicates versions so the DB contains **only distinct bodies** per symbol (avoid storing identical code repeatedly).
4. Stores results in **DuckDB** as the source of truth (single local file database).
5. Produces stable IDs and metadata so later steps can reference definitions reliably.

### Implementation plan requirements

Create a clear plan (no full code) that covers:

* Modules/components to implement
* Data model and stable identifiers
* Mining strategy and performance tactics
* Key gotchas and how to handle them
* Minimal CLI / entrypoints for running against a repo

### Core libraries and why

Use these libraries unless you have a compelling reason to swap:

* **PyDriller**: traverse git commits and access file snapshots (`source_code` / `source_code_before`) and file diffs; simplest way to mine history without manual checkouts. Gotcha: merge commits may have empty modifications; plan around this.
* **LibCST**: parse Python source losslessly and extract exact code for `FunctionDef` and `ClassDef` nodes with accurate start/end locations. This is important because we want the *exact source* stored for later use and optional formatting-sensitive comparisons.
* **DuckDB**: canonical storage for symbol/version tables; easy analytics, easy export to Parquet later, strong performance for append-heavy workloads.
* (Optional now, but plan for later) **ChromaDB**: vector index for similarity search across extracted versions; not the canonical DB.

### Data model (DuckDB)

Design around stable keys:

* `symbol_key = "{repo_id}:{module}:{qualname}:{kind}"`
* `version_key = "{symbol_key}:{code_hash}"` (or include commit hash if needed, but prefer content-based dedupe)
  Store at minimum:
* repo_id (string, derived from URL/path)
* commit_hash, commit_time
* file_path, module (dotted path), start_line, end_line
* kind: function | class (and optionally method; or treat method as function with qualname `Class.method`)
* qualname (inside-module), plus fully-qualified `module.qualname`
* code (exact text)
* code_hash (sha256 of code)
* docstring (optional)
* `extra_json` (JSON): placeholder for future metadata (referenced names, imports, decorators, defaults, etc.)

Upsert/dedupe strategy:

* Ensure `version_key` is unique. Insert new versions and ignore duplicates.
* Store `symbols` table separately for cataloging, or embed symbol attributes in versions table; justify your choice.

### Mining strategy (commit-level v0)

* Traverse commits using PyDriller; prefer `only_modifications_with_file_types=['.py']`.
* Consider excluding merge commits (`only_no_merge=True`) to avoid empty modifications and confusing diffs.
* Optionally support filtering by author(s) for “my commits only” mode.
* For each modified `.py` file, prefer parsing `mf.source_code` (post-commit snapshot). You don’t need to reconstruct patches.
* Extract definitions from the full file snapshot (not just diff hunks) to avoid partial-context issues.

Performance guidance (important)
Plan for many repos, potentially large histories. Include tactics such as:

* Skip non-Python files early.
* Hash whole file content and short-circuit extraction if identical file content was already processed for that path (optional cache).
* Deduplicate versions aggressively via `code_hash`/`version_key` to reduce writes.
* Consider a “fast mode” option:

  * Use PyDriller’s changed file list and parse only those files
  * Avoid scope analysis in v0 (no heavy cross-module resolution now)
* Make parsing failures non-fatal (log and continue).

### Extraction details (LibCST)

* Use LibCST metadata (PositionProvider) to record start/end positions and extract exact code text for each node.
* Determine qualnames:

  * Track class nesting so methods become `ClassName.method`
  * Decide whether nested functions are included (document decision; optional in v0)
* Extract docstrings if available; store separately.

### Constants and “dependencies used by a function”

For v0:

* It’s enough to store a placeholder in `extra_json` and/or store module-level assignments as separate “constant” symbols if easy.
* Do NOT implement full cross-module resolution in v0.
* If you include name references:

  * Keep it lightweight; just record identifiers referenced inside the function body (best-effort), to enable later linking.

### Gotchas / edge cases to explicitly address in the plan

* Merge commits in PyDriller can have empty modifications; do not rely on merge commits for PR-level semantics.
* Large repos: commit traversal time; ensure progress logging and resumability (e.g., store last processed commit, or allow `--since` commit/time).
* Syntax changes across Python versions: LibCST generally handles modern Python, but files may contain syntax unsupported by the environment; handle parse errors gracefully.
* Renames: `old_path` vs `new_path` in modifications; track correct path/module.
* Generated files / vendored code: allow ignore patterns (e.g. `site-packages`, `venv`, `build/`, `dist/`, `*_pb2.py`).
* Duplicate qualnames across modules: ensure module included in keys.
* Encoding: handle non-utf8 files; prefer robust decode or skip with warning.

### Deliverables (what to produce)

1. A written implementation plan with components and responsibilities.
2. DuckDB schema definition (DDL) and key indexes recommended.
3. CLI design proposal (e.g., `extract_repo --repo <path_or_url> --db <file> [--authors ...] [--since ...] [--no-merge] [--ignore ...]`).
4. Logging / metrics recommendations for throughput and error counts.
5. A `potential_extensions.md` section (see below).

---

## Section to add to `potential_extensions.md`

Add a short list of optional libraries and what they could enable later:

* **ChromaDB**: store embeddings for each `version_key` to support semantic similarity search (find similar functions, cluster variants). Keep DuckDB as canonical; use Chroma as an index keyed by `version_key`.
* **Griffe**: extract signatures/docstrings and a structured API model without importing code; useful for API-diff analysis over time and documentation-oriented views.
* **Jedi**: deeper static analysis like “go to definition” / reference resolution; could help link function references to definitions across modules.
* **tree-sitter (python grammar)**: fast parsing to identify definition spans quickly; can be used as a speed layer before LibCST for exact source extraction.
* **unidiff**: if later you ingest PR diffs/patches directly (e.g., from GitHub API/gh CLI), parse unified diff text reliably.
* **GitHub CLI / GitHub API**: for PR-level grouping and metadata enrichment; can map commits to PRs and store PR IDs/titles/labels. Note: PR diffs can be large/truncated; commit-level mining is more reliable.

---

**Your task:** produce the plan and the notes above. Avoid writing full implementation code. Small syntax snippets are OK only to illustrate gotchas (e.g., how to configure PyDriller filters or DuckDB MERGE/unique constraints).

