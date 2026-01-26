import logging

import libcst as cst
from libcst.metadata import MetadataWrapper

from codearc.extraction.symbol_extractor import SymbolExtractor
from codearc.models.extracted_symbol import ExtractedSymbol

logger = logging.getLogger(__name__)


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
        logger.warning("Failed to extract symbols: %s", e, exc_info=True)
        return []

    return extractor.symbols
