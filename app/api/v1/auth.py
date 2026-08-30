from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_bearer_token, get_current_user
from app.models.user import UserCreate
from app.schemas.auth import (
    AuthUser,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    SocialLoginRequest,
    SocialLoginResponse,
)
from app.schemas.common import error_response, success_response
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register")
def register(
    body: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        result = auth_service.register(
            UserCreate(name=body.name, email=body.email, password=body.password)
        )
        return success_response(
            result.model_dump(),
            "Account created successfully",
            status_code=201,
        )
    except ValueError as exc:
        if str(exc) == "EMAIL_EXISTS":
            return error_response(
                "An account with this email already exists.",
                status_code=409,
                code="EMAIL_EXISTS",
            )
        raise


@router.post("/login")
def login(
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    if not body.email.strip() or not body.password.strip():
        return error_response(
            "Email and password are required.",
            status_code=400,
            code="VALIDATION_ERROR",
        )

    try:
        result = auth_service.login(body.email, body.password)
        return success_response(result.model_dump(), "Login successful")
    except ValueError as exc:
        if str(exc) == "INVALID_CREDENTIALS":
            return error_response(
                "Invalid email or password. Try demo@discipline.os / password123",
                status_code=401,
                code="INVALID_CREDENTIALS",
            )
        if str(exc) == "ACCOUNT_DISABLED":
            return error_response(
                "This account has been disabled.",
                status_code=403,
                code="ACCOUNT_DISABLED",
            )
        raise


@router.get("/me")
def me(current_user: Annotated[AuthUser, Depends(get_current_user)]):
    return success_response(current_user.model_dump())


@router.post("/logout")
def logout(
    token: Annotated[str | None, Depends(get_bearer_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    if token:
        try:
            auth_service.logout(token)
        except ValueError:
            pass
    return success_response(None, "Logged out successfully")


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    result = auth_service.forgot_password(body.email)
    return success_response(result.model_dump(), result.message)


@router.post("/social")
def social_login(
    body: SocialLoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    result = auth_service.social_login_stub(body.provider)
    provider_label = body.provider.capitalize()
    response = SocialLoginResponse(
        token=result.token,
        user=result.user,
        provider=body.provider,
    )
    return success_response(
        response.model_dump(),
        f"Successfully signed in with {provider_label}",
    )
