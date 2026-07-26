from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class SourceLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: str | None = None
    storage_uri: str | None = None
    raw_object_id: str | None = None
    source_document_id: str | None = None
    document_version: str | None = None
    page: int | None = Field(default=None, ge=1)
    table: str | None = None
    row: str | None = None
    json_pointer: str | None = None
    text_span: str | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=1)
    quoted_text_hash: str | None = None
    table_cell: str | None = None
    bounding_box: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def require_location(self) -> SourceLocator:
        if not any(
            (
                self.uri,
                self.storage_uri,
                self.raw_object_id,
                self.source_document_id,
                self.document_version,
                self.page,
                self.table,
                self.row,
                self.json_pointer,
                self.text_span,
                self.char_start is not None,
                self.char_end is not None,
                self.quoted_text_hash,
                self.table_cell,
                self.bounding_box,
            )
        ):
            raise ValueError("source locator must identify at least one location")
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be supplied together")
        if self.char_start is not None and self.char_end is not None:
            if self.char_end <= self.char_start:
                raise ValueError("char_end must be greater than char_start")
        if self.bounding_box is not None:
            left, top, right, bottom = self.bounding_box
            if right <= left or bottom <= top:
                raise ValueError("bounding_box must have positive width and height")
        return self

    @property
    def locator_hash(self) -> str:
        return canonical_hash(self, prefix="source_locator:")
