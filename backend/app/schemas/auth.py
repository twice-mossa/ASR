from pydantic import BaseModel, EmailStr, Field


class UserProfile(BaseModel):
    id: int
    username: str
    email: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user: UserProfile


class LogoutResponse(BaseModel):
    message: str
