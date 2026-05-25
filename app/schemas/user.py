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


class AdminUserItem(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UsersByStatus(BaseModel):
    pending: list[AdminUserItem]
    approved: list[AdminUserItem]
    rejected: list[AdminUserItem]


class AdminUserListResponse(BaseModel):
    admins: list[AdminUserItem]
    users: UsersByStatus


class UserResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: UserRole
    status: ApprovalStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
