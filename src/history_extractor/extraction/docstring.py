import libcst as cst


def extract_string_content(raw: str) -> str | None:
    """Extract content from a string literal, handling prefixes and quotes."""
    # Strip string prefixes (r, u, f, b, fr, rf, br, rb, etc.)
    quote_start = 0
    while quote_start < len(raw) and raw[quote_start] not in ('"', "'"):
        quote_start += 1
    raw = raw[quote_start:]

    # Handle triple quotes
    if raw.startswith(('"""', "'''")):
        return raw[3:-3]
    # Handle single quotes
    if raw.startswith(('"', "'")):
        return raw[1:-1]
    return None


def collect_string_parts(
    node: cst.BaseString,
    parts: list[str],
) -> None:
    """Recursively collect string parts from a potentially nested ConcatenatedString."""
    if isinstance(node, cst.SimpleString):
        content = extract_string_content(node.value)
        if content is not None:
            parts.append(content)
    elif isinstance(node, cst.ConcatenatedString):
        collect_string_parts(node.left, parts)
        collect_string_parts(node.right, parts)
    # FormattedString (f-strings) are ignored for docstrings


def get_docstring(body: cst.BaseSuite) -> str | None:
    """Extract docstring from a function or class body."""
    if not isinstance(body, cst.IndentedBlock):
        return None

    if not body.body:
        return None

    first_stmt = body.body[0]
    if not isinstance(first_stmt, cst.SimpleStatementLine):
        return None

    if not first_stmt.body:
        return None

    first_expr = first_stmt.body[0]
    if not isinstance(first_expr, cst.Expr):
        return None

    value = first_expr.value
    if isinstance(value, cst.SimpleString):
        return extract_string_content(value.value)

    if isinstance(value, cst.ConcatenatedString):
        # Handle concatenated strings (rare for docstrings but possible)
        # ConcatenatedString can nest: "a" "b" "c" becomes
        # ConcatenatedString(left=ConcatenatedString(left="a", right="b"), right="c")
        parts: list[str] = []
        collect_string_parts(value, parts)
        return "".join(parts) if parts else None

    return None
