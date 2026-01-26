from pydantic import BaseModel, Field


class EncodingConfig(BaseModel):
    """Encoding fallbacks for reading source files."""

    encodings: list[str] = Field(default=["utf-8", "cp1252", "latin-1"])
