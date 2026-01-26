from pathlib import Path

from codearc.utils import compute_code_hash, file_path_to_module, safe_decode


class TestComputeCodeHash:
    def test_deterministic(self) -> None:
        code = "def foo(): pass"
        hash1 = compute_code_hash(code)
        hash2 = compute_code_hash(code)
        assert hash1 == hash2

    def test_different_code_different_hash(self) -> None:
        hash1 = compute_code_hash("def foo(): pass")
        hash2 = compute_code_hash("def bar(): pass")
        assert hash1 != hash2

    def test_hash_length(self) -> None:
        h = compute_code_hash("def foo(): pass")
        assert len(h) == 16

    def test_whitespace_matters(self) -> None:
        hash1 = compute_code_hash("def foo(): pass")
        hash2 = compute_code_hash("def foo():  pass")
        assert hash1 != hash2


class TestFilePathToModule:
    def test_simple_path(self, tmp_path: Path) -> None:
        result = file_path_to_module("foo/bar.py", tmp_path)
        assert result == "foo.bar"

    def test_with_src_directory(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        result = file_path_to_module("src/mypackage/utils.py", tmp_path)
        assert result == "mypackage.utils"

    def test_with_explicit_package_root(self, tmp_path: Path) -> None:
        package_root = tmp_path / "lib"
        package_root.mkdir()
        result = file_path_to_module(
            "lib/mypackage/core.py", tmp_path, package_root=package_root
        )
        assert result == "mypackage.core"

    def test_init_file(self, tmp_path: Path) -> None:
        result = file_path_to_module("mypackage/__init__.py", tmp_path)
        assert result == "mypackage"

    def test_nested_init_file(self, tmp_path: Path) -> None:
        result = file_path_to_module("mypackage/sub/__init__.py", tmp_path)
        assert result == "mypackage.sub"

    def test_single_file(self, tmp_path: Path) -> None:
        result = file_path_to_module("script.py", tmp_path)
        assert result == "script"


class TestSafeDecode:
    def test_utf8(self) -> None:
        content = b"hello world"
        result = safe_decode(content)
        assert result == "hello world"

    def test_latin1_fallback(self) -> None:
        # Byte that's valid in latin-1 but not utf-8
        content = b"caf\xe9"
        result = safe_decode(content)
        assert result == "café"

    def test_all_fail_returns_none(self) -> None:
        # Bytes that can't be decoded by common encodings
        content = b"\xff\xfe\x00\x01"
        result = safe_decode(content, encodings=["ascii"])
        assert result is None

    def test_custom_encodings(self) -> None:
        content = "hello".encode("utf-16")
        result = safe_decode(content, encodings=["utf-16"])
        assert result == "hello"

    def test_empty_bytes(self) -> None:
        result = safe_decode(b"")
        assert result == ""
