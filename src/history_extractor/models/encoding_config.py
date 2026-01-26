from pydantic import BaseModel, Field


class EncodingConfig(BaseModel):
    """Encoding fallbacks for reading source files."""

    encodings: list[str] = Field(default=["utf-8", "latin-1", "cp1252", "iso-8859-1"])
