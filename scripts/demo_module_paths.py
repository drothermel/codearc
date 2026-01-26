#!/usr/bin/env python3
"""Demo: Show module path resolution for different file layouts."""

import tempfile
from pathlib import Path

from codearc.utils import file_path_to_module


def main() -> None:
    print("=== Module Path Resolution Demo ===")
    print("file_path_to_module converts file paths to Python module paths.")
    print("It handles different project layouts automatically.\n")

    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        # Demo 1: Simple layout (no src/)
        print("--- Layout 1: Simple (no src/) ---")
        print("  Project structure:")
        print("    myproject/")
        print("      mypackage/")
        print("        __init__.py")
        print("        utils.py")
        print("        sub/")
        print("          helpers.py")
        print()

        cases = [
            ("mypackage/utils.py", "mypackage.utils"),
            ("mypackage/__init__.py", "mypackage"),
            ("mypackage/sub/helpers.py", "mypackage.sub.helpers"),
            ("script.py", "script"),
        ]

        for file_path, expected in cases:
            result = file_path_to_module(file_path, repo_root)
            status = "OK" if result == expected else "MISMATCH"
            print(f"  {file_path:30} -> {result:25} [{status}]")

        # Demo 2: src/ layout
        print("\n--- Layout 2: src/ layout ---")
        print("  Project structure:")
        print("    myproject/")
        print("      src/")
        print("        mypackage/")
        print("          core.py")
        print()

        (repo_root / "src").mkdir()

        cases = [
            ("src/mypackage/core.py", "mypackage.core"),
            ("src/mypackage/__init__.py", "mypackage"),
        ]

        for file_path, expected in cases:
            result = file_path_to_module(file_path, repo_root)
            status = "OK" if result == expected else "MISMATCH"
            print(f"  {file_path:30} -> {result:25} [{status}]")

        # Demo 3: Explicit package root
        print("\n--- Layout 3: Explicit package_root ---")
        print("  When you specify package_root, it overrides auto-detection.")
        print()

        package_root = repo_root / "lib" / "python"
        package_root.mkdir(parents=True)
        cases = [
            ("lib/python/mypackage/core.py", "mypackage.core"),
        ]

        for file_path, expected in cases:
            result = file_path_to_module(file_path, repo_root, package_root)
            status = "OK" if result == expected else "MISMATCH"
            print(f"  {file_path:30} -> {result:25} [{status}]")
            print(f"    (with package_root={package_root.relative_to(repo_root)})")

    print("\n--- Resolution Order ---")
    print("  1. If package_root provided, use it")
    print("  2. Else if src/ exists, use src/ as base")
    print("  3. Else use repo root as base")


if __name__ == "__main__":
    main()
