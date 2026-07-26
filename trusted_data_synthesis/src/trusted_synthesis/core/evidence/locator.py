from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: str | None = None
    storage_uri: str | None = None
    raw_object_id: str | None = None
    source_document_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    table: str | None = None
    row: str | None = None
    json_pointer: str | None = None
    text_span: str | None = None

    @model_validator(mode="after")
    def require_location(self) -> SourceLocator:
        if not any(
            (
                self.uri,
                self.storage_uri,
                self.raw_object_id,
                self.source_document_id,
                self.page,
                self.table,
                self.row,
                self.json_pointer,
                self.text_span,
            )
        ):
            raise ValueError("source locator must identify at least one location")
        return self
