import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import ApprovalStatus, UserRole


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None

class UserProfileResponse(BaseModel):
    name: str
    email: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: UserRole
    status: ApprovalStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
