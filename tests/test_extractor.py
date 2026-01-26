from codearc.extraction.extract_symbols import extract_symbols


class TestExtractSymbols:
    def test_extract_function(self) -> None:
        code = "def foo():\n    pass"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "foo"
        assert symbols[0].qualname == "foo"
        assert symbols[0].kind == "function"
        assert symbols[0].start_line == 1
        assert symbols[0].end_line == 2

    def test_extract_class(self) -> None:
        code = "class MyClass:\n    pass"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "MyClass"
        assert symbols[0].qualname == "MyClass"
        assert symbols[0].kind == "class"

    def test_extract_method(self) -> None:
        code = "class MyClass:\n    def my_method(self):\n        pass"
        symbols = extract_symbols(code)
        assert len(symbols) == 2
        # Class comes first
        assert symbols[0].name == "MyClass"
        assert symbols[0].kind == "class"
        # Method has qualified name
        assert symbols[1].name == "my_method"
        assert symbols[1].qualname == "MyClass.my_method"
        assert symbols[1].kind == "function"

    def test_nested_function_skipped(self) -> None:
        code = """def outer():
    def inner():
        pass
    return inner
"""
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "outer"

    def test_nested_class_method(self) -> None:
        code = """class Outer:
    class Inner:
        def method(self):
            pass
"""
        symbols = extract_symbols(code)
        names = [(s.name, s.qualname) for s in symbols]
        assert ("Outer", "Outer") in names
        assert ("Inner", "Outer.Inner") in names
        assert ("method", "Outer.Inner.method") in names

    def test_docstring_extraction(self) -> None:
        code = '''def foo():
    """This is a docstring."""
    pass
'''
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].docstring == "This is a docstring."

    def test_docstring_single_quotes(self) -> None:
        code = """def foo():
    '''Single quote docstring.'''
    pass
"""
        symbols = extract_symbols(code)
        assert symbols[0].docstring == "Single quote docstring."

    def test_docstring_with_prefix(self) -> None:
        # Raw string docstring (common for regex examples)
        code = r'''def foo():
    r"""Raw docstring with \n escape."""
    pass
'''
        symbols = extract_symbols(code)
        assert symbols[0].docstring == r"Raw docstring with \n escape."

    def test_docstring_unicode_prefix(self) -> None:
        # Unicode prefix (Python 2/3 compatible code)
        code = '''def foo():
    u"""Unicode docstring."""
    pass
'''
        symbols = extract_symbols(code)
        assert symbols[0].docstring == "Unicode docstring."

    def test_docstring_concatenated(self) -> None:
        # Concatenated string docstring (multiple parts)
        code = """def foo():
    "Part one. " "Part two. " "Part three."
    pass
"""
        symbols = extract_symbols(code)
        assert symbols[0].docstring == "Part one. Part two. Part three."

    def test_no_docstring(self) -> None:
        code = "def foo():\n    x = 1"
        symbols = extract_symbols(code)
        assert symbols[0].docstring is None

    def test_code_preserved(self) -> None:
        code = "def foo(x, y):\n    return x + y"
        symbols = extract_symbols(code)
        # LibCST may add trailing newline, so compare stripped
        assert symbols[0].code.strip() == code.strip()

    def test_multiple_functions(self) -> None:
        code = """def foo():
    pass

def bar():
    pass
"""
        symbols = extract_symbols(code)
        assert len(symbols) == 2
        assert symbols[0].name == "foo"
        assert symbols[1].name == "bar"

    def test_syntax_error_returns_empty(self) -> None:
        code = "def foo(\n    # missing closing paren"
        symbols = extract_symbols(code)
        assert symbols == []

    def test_empty_file(self) -> None:
        code = ""
        symbols = extract_symbols(code)
        assert symbols == []

    def test_only_imports(self) -> None:
        code = "import os\nfrom sys import path"
        symbols = extract_symbols(code)
        assert symbols == []

    def test_async_function(self) -> None:
        code = "async def fetch():\n    pass"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "fetch"
        assert symbols[0].kind == "function"

    def test_decorated_function(self) -> None:
        code = "@decorator\ndef foo():\n    pass"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "foo"
        assert "@decorator" in symbols[0].code

    def test_class_with_docstring(self) -> None:
        code = '''class MyClass:
    """Class docstring."""
    pass
'''
        symbols = extract_symbols(code)
        assert symbols[0].docstring == "Class docstring."
