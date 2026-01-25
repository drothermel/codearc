from datetime import UTC, datetime
from pathlib import Path

import pytest

from history_extractor.models.config import (
    EncodingConfig,
    ExtractionConfig,
    IgnorePatterns,
)
from history_extractor.models.stats import MiningStats
from history_extractor.models.symbol import ExtractedSymbol, SymbolVersion


class TestIgnorePatterns:
    def test_default_patterns_exist(self) -> None:
        patterns = IgnorePatterns()
        assert len(patterns.patterns) > 0
        assert "**/venv/**" in patterns.patterns

    def test_matches_venv(self) -> None:
        patterns = IgnorePatterns()
        assert patterns.matches("project/venv/lib/foo.py")
        assert patterns.matches(".venv/bin/activate")

    def test_matches_pycache(self) -> None:
        patterns = IgnorePatterns()
        # Nested __pycache__
        assert patterns.matches("src/__pycache__/foo.cpython-312.pyc")
        # Root-level __pycache__
        assert patterns.matches("__pycache__/foo.cpython-312.pyc")

    def test_matches_pb2(self) -> None:
        patterns = IgnorePatterns()
        assert patterns.matches("proto/service_pb2.py")
        assert patterns.matches("some_pb2_grpc.py")

    def test_does_not_match_normal_files(self) -> None:
        patterns = IgnorePatterns()
        assert not patterns.matches("src/main.py")
        assert not patterns.matches("tests/test_foo.py")

    def test_custom_patterns(self) -> None:
        patterns = IgnorePatterns(patterns=["*.generated.py"])
        assert patterns.matches("foo.generated.py")
        assert not patterns.matches("foo.py")


class TestEncodingConfig:
    def test_default_encodings(self) -> None:
        config = EncodingConfig()
        assert "utf-8" in config.encodings
        assert len(config.encodings) >= 2


class TestExtractionConfig:
    def test_minimal_config(self) -> None:
        config = ExtractionConfig(
            repo_path=Path("/tmp/repo"),
            db_path=Path("/tmp/out.duckdb"),
        )
        assert config.repo_path == Path("/tmp/repo")
        assert config.skip_merge_commits is True
        assert config.authors is None

    def test_get_repo_id_from_path(self) -> None:
        config = ExtractionConfig(
            repo_path=Path("/home/user/my-project"),
            db_path=Path("/tmp/out.duckdb"),
        )
        assert config.get_repo_id() == "my-project"

    def test_get_repo_id_explicit(self) -> None:
        config = ExtractionConfig(
            repo_path=Path("/tmp/repo"),
            db_path=Path("/tmp/out.duckdb"),
            repo_id="custom-id",
        )
        assert config.get_repo_id() == "custom-id"


class TestExtractedSymbol:
    def test_create_function(self) -> None:
        symbol = ExtractedSymbol(
            name="foo",
            qualname="foo",
            kind="function",
            code="def foo(): pass",
            start_line=1,
            end_line=1,
        )
        assert symbol.kind == "function"
        assert symbol.docstring is None

    def test_create_method(self) -> None:
        symbol = ExtractedSymbol(
            name="bar",
            qualname="MyClass.bar",
            kind="function",
            code="def bar(self): pass",
            start_line=5,
            end_line=5,
            docstring="A method.",
        )
        assert symbol.qualname == "MyClass.bar"
        assert symbol.docstring == "A method."


class TestSymbolVersion:
    @pytest.fixture
    def sample_version(self) -> SymbolVersion:
        return SymbolVersion(
            repo_id="test-repo",
            commit_hash="abc123",
            commit_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
            file_path="src/foo.py",
            module="foo",
            name="bar",
            qualname="bar",
            kind="function",
            code="def bar(): pass",
            code_hash="deadbeef",
            start_line=1,
            end_line=1,
        )

    def test_symbol_key(self, sample_version: SymbolVersion) -> None:
        assert sample_version.symbol_key == "test-repo:foo:bar:function"

    def test_version_key(self, sample_version: SymbolVersion) -> None:
        assert sample_version.version_key == "test-repo:foo:bar:function:deadbeef"

    def test_to_db_tuple(self, sample_version: SymbolVersion) -> None:
        t = sample_version.to_db_tuple()
        assert len(t) == 15
        assert t[0] == sample_version.version_key
        assert t[1] == sample_version.symbol_key
        assert t[2] == "test-repo"


class TestMiningStats:
    def test_initial_values(self) -> None:
        stats = MiningStats()
        assert stats.commits_processed == 0
        assert stats.symbols_extracted == 0

    def test_increment_methods(self) -> None:
        stats = MiningStats()
        stats.increment_commits_processed()
        stats.increment_commits_processed()
        stats.add_symbols(5)
        assert stats.commits_processed == 2
        assert stats.symbols_extracted == 5

    def test_summary(self) -> None:
        stats = MiningStats(commits_processed=10, symbols_extracted=100)
        summary = stats.summary()
        assert "10" in summary
        assert "100" in summary
