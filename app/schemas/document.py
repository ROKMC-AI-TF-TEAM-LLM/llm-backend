from datetime import datetime

from pydantic import BaseModel


class DocumentItem(BaseModel):
    name: str
    type: str | None = None
    applied_at: datetime | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentItem]
    has_more: bool
    total: int | None = None
