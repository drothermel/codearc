from fnmatch import fnmatch

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
            "__pycache__/**",
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

        return any(fnmatch(path, pattern) for pattern in self.patterns)
