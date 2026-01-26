#!/usr/bin/env python3
"""Demo: Parse Python code and extract symbols."""

from codearc.extraction.extract_symbols import extract_symbols

SAMPLE_CODE = '''
class DataProcessor:
    """Process data from various sources."""

    def __init__(self, source: str):
        self.source = source

    def process(self, data: list) -> dict:
        """Process the input data and return results."""
        return {"source": self.source, "count": len(data)}

    class Config:
        """Configuration for the processor."""
        default_timeout = 30


def helper_function(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


async def fetch_data(url: str) -> bytes:
    """Fetch data from a URL."""
    pass
'''


def main() -> None:
    print("=== Extractor Demo ===")
    print("The extractor uses LibCST to parse Python code and extract")
    print("all functions and classes with their metadata.\n")

    print("--- Sample Code ---")
    for i, line in enumerate(SAMPLE_CODE.strip().split("\n"), 1):
        print(f"  {i:2}: {line}")

    print("\n--- Extracted Symbols ---")
    symbols = extract_symbols(SAMPLE_CODE)

    for sym in symbols:
        print(f"\n  {sym.kind.upper()}: {sym.qualname}")
        print(f"    Lines: {sym.start_line}-{sym.end_line}")
        if sym.docstring:
            # Truncate long docstrings
            doc = sym.docstring.replace("\n", " ")[:50]
            suffix = "..." if len(sym.docstring) > 50 else ""
            print(f"    Docstring: {doc}{suffix}")
        # Show first non-empty line of code
        first_line = sym.code.strip().split("\n")[0][:60]
        print(f"    Code: {first_line}")

    print("\n--- Summary ---")
    funcs = [s for s in symbols if s.kind == "function"]
    classes = [s for s in symbols if s.kind == "class"]
    print(f"  Functions: {len(funcs)}")
    print(f"  Classes: {len(classes)}")

    print("\n--- Qualname Examples ---")
    print("  Notice how methods get qualified names:")
    for sym in symbols:
        if "." in sym.qualname:
            print(f"    {sym.name} -> {sym.qualname}")


if __name__ == "__main__":
    main()
