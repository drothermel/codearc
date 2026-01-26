import libcst as cst
from libcst.metadata import PositionProvider

from codearc.extraction.docstring import get_docstring
from codearc.models.extracted_symbol import ExtractedSymbol, SymbolKind


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
        docstring = get_docstring(node.body)

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
