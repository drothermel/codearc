from typing import Literal

from pydantic import BaseModel, Field

SymbolKind = Literal["function", "class"]


class ExtractedSymbol(BaseModel):
    """A symbol extracted from a single file parse."""

    name: str = Field(description="Simple name of the symbol")
    qualname: str = Field(description="Qualified name (e.g., ClassName.method_name)")
    kind: SymbolKind = Field(description="Type of symbol")
    code: str = Field(description="Full source code of the symbol")
    start_line: int = Field(description="Starting line number (1-indexed)")
    end_line: int = Field(description="Ending line number (1-indexed)")
    docstring: str | None = Field(default=None, description="Docstring if present")
