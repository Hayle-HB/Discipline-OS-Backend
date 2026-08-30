from typing import Annotated

from fastapi import Depends, Header

from app.core.exceptions import AppError
from app.models.user import UserCreate
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthUser
from app.services.auth_service import AuthService


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repository)


def get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(
    token: Annotated[str | None, Depends(get_bearer_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthUser:
    if not token:
        raise AppError(
            "Missing or invalid authorization token.",
            status_code=401,
            code="UNAUTHORIZED",
        )

    try:
        return auth_service.get_current_user(token)
    except ValueError as exc:
        code = str(exc)
        if code == "USER_NOT_FOUND":
            raise AppError("User not found.", status_code=404, code="USER_NOT_FOUND") from exc
        raise AppError(
            "Invalid or expired token.",
            status_code=401,
            code="INVALID_TOKEN",
        ) from exc
