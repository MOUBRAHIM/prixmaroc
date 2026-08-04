from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: str | None = None
    phone: str | None = None
    city: str | None = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    city: str | None = None
    password: str | None = Field(None, min_length=8)


class UserRead(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    fcm_token: str | None = None
    avatar_url: str | None = None
    preferred_stores: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserFCMUpdate(BaseModel):
    fcm_token: str | None = None
    avatar_url: str | None = None
    preferred_stores: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: int  # user id
