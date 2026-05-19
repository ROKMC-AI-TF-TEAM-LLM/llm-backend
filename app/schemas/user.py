import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None


class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
