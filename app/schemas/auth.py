from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: str  # Can be user email or employee code (e.g. EMP0007)
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TokenUser(BaseModel):
    id: int
    employee_id: Optional[int] = None
    role: str
    full_name: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: TokenUser


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: int
    employee_id: Optional[int] = None
    email: str
    role: str
