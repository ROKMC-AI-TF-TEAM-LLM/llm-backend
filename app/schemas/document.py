from datetime import datetime
from uuid import UUID
from app.models.document import IndexStatusEnum
from pydantic import BaseModel, ConfigDict



class DocumentItem(BaseModel):
    name: str
    type: str | None = None
    domain: str | None = None
    visibility: str | None = None
    owning_department: str | None = None
    applied_at: datetime | None = None
    

class AdminDocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id : UUID 
    name: str
    content_type: str | None = None # type이 없음, type은 MARS에서 주는거라서, 추후 content type을 잘 가공해서 파일 확장자만 남기기. 
    domain: str | None = None
    visibility: str | None = None
    department: str | None = None
    status: IndexStatusEnum | None = None
    created_at: datetime | None = None
    size: int | None = None

    



class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: UUID
    name: str
    domain: str
    visibility: str
    status: IndexStatusEnum
    created_at: datetime


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: UUID
    status: IndexStatusEnum
    chunks_indexed: int | None = None
    error: str | None = None


class AdminDocumentListResponse(BaseModel):
    documents: list[AdminDocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool

class DocumentDeleteResponse(BaseModel):
    document_id: UUID
    deleted_chunks: int