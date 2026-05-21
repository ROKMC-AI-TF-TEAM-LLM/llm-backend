from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    detail: str


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    status_code: int
    data: T | None = None
    error: ErrorDetail | None = None

    @classmethod
    def ok(cls, data: T = None, status_code: int = 200) -> "ApiResponse[T]":
        return cls(success=True, status_code=status_code, data=data)

    @classmethod
    def fail(cls, code: str, detail: str, status_code: int = 500) -> "ApiResponse[None]":
        return cls(success=False, status_code=status_code, error=ErrorDetail(code=code, detail=detail))
