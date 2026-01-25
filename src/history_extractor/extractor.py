import logging

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from history_extractor.models.symbol import ExtractedSymbol, SymbolKind

logger = logging.getLogger(__name__)


def _get_docstring(body: cst.BaseSuite) -> str | None:
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
        # Remove quotes and unescape
        raw = value.value
        # Handle triple quotes
        if raw.startswith(('"""', "'''")):
            return raw[3:-3]
        # Handle single quotes
        if raw.startswith(('"', "'")):
            return raw[1:-1]

    if isinstance(value, cst.ConcatenatedString):
        # Handle concatenated strings (rare for docstrings but possible)
        parts = []
        for part in value.left, value.right:
            if isinstance(part, cst.SimpleString):
                raw = part.value
                if raw.startswith(('"""', "'''")):
                    parts.append(raw[3:-3])
                elif raw.startswith(('"', "'")):
                    parts.append(raw[1:-1])
        return "".join(parts) if parts else None

    return None


class SymbolExtractor(cst.CSTVisitor):
    """Extract functions and classes from a Python module."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, module: cst.Module) -> None:
        self.module = module
        self.class_stack: list[str] = []
        self.symbols: list[ExtractedSymbol] = []

    def _get_position(self, node: cst.CSTNode) -> tuple[int, int]:
        """Get start and end line numbers for a node."""
        pos = self.get_metadata(PositionProvider, node)
        return pos.start.line, pos.end.line

    def _create_symbol(
        self,
        node: cst.FunctionDef | cst.ClassDef,
        kind: SymbolKind,
    ) -> ExtractedSymbol:
        """Create an ExtractedSymbol from a node."""
        name = node.name.value
        if self.class_stack:
            qualname = ".".join([*self.class_stack, name])
        else:
            qualname = name
        start_line, end_line = self._get_position(node)
        code = self.module.code_for_node(node)
        docstring = _get_docstring(node.body)

        return ExtractedSymbol(
            name=name,
            qualname=qualname,
            kind=kind,
            code=code,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
        )

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Visit a class definition."""
        self.symbols.append(self._create_symbol(node, "class"))
        self.class_stack.append(node.name.value)
        return True  # Visit methods inside the class

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        """Leave a class definition."""
        self.class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        """Visit a function definition."""
        self.symbols.append(self._create_symbol(node, "function"))
        return False  # Don't visit nested functions


def extract_symbols(source_code: str) -> list[ExtractedSymbol]:
    """
    Extract all functions and classes from Python source code.

    Returns empty list if parsing fails.
    """
    try:
        module = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        logger.warning("Failed to parse source: %s", e)
        return []

    wrapper = MetadataWrapper(module)
    extractor = SymbolExtractor(module)

    try:
        wrapper.visit(extractor)
    except Exception as e:
        logger.warning("Failed to extract symbols: %s", e)
        return []

    return extractor.symbols
