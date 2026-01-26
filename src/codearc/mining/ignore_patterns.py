from fnmatch import fnmatch

from pydantic import BaseModel, Field


class IgnorePatterns(BaseModel):
    """Glob patterns for files/directories to skip during extraction."""

    patterns: list[str] = Field(
        default=[
            "**/venv/**",
            "**/.venv/**",
            "**/site-packages/**",
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/.git/**",
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
        return any(fnmatch(path, p) for p in self._expanded_patterns())

    def _expanded_patterns(self) -> list[str]:
        """Expand **/ patterns to also match at root level.

        fnmatch treats ** as two wildcards, not as globstar. This means
        **/venv/** won't match venv/foo.py (no leading path). By expanding
        patterns that start with **/, we ensure root-level matches work.
        """
        expanded = []
        for p in self.patterns:
            expanded.append(p)
            if p.startswith("**/"):
                expanded.append(p[3:])
        return expanded
