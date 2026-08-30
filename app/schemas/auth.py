from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class AuthUser(BaseModel):
    id: str
    email: EmailStr
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    rememberMe: bool | None = None


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthTokenResponse(BaseModel):
    token: str
    user: AuthUser


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class SocialLoginRequest(BaseModel):
    provider: Literal["google", "apple"]


class SocialLoginResponse(AuthTokenResponse):
    provider: str
