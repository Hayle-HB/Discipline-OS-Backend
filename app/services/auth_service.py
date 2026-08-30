from app.core.security import create_access_token, verify_password
from app.models.user import UserCreate, UserInDB
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthTokenResponse, AuthUser, ForgotPasswordResponse


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository
        self._revoked_tokens: set[str] = set()

    def register(self, data: UserCreate) -> AuthTokenResponse:
        try:
            user = self._users.create(data)
        except ValueError as exc:
            if str(exc) == "EMAIL_EXISTS":
                raise ValueError("EMAIL_EXISTS") from exc
            raise

        token, token_id = create_access_token(user.id)
        return self._build_auth_response(token, user)

    def login(self, email: str, password: str) -> AuthTokenResponse:
        user = self._users.find_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("INVALID_CREDENTIALS")

        if not user.is_active:
            raise ValueError("ACCOUNT_DISABLED")

        token, token_id = create_access_token(user.id)
        return self._build_auth_response(token, user)

    def get_current_user(self, token: str) -> AuthUser:
        payload = self._decode_active_token(token)
        user = self._users.find_by_id(payload["sub"])
        if not user or not user.is_active:
            raise ValueError("USER_NOT_FOUND")
        return AuthUser(**user.to_public())

    def logout(self, token: str) -> None:
        payload = self._decode_active_token(token, allow_revoked=True)
        token_id = payload.get("jti")
        if token_id:
            self._revoked_tokens.add(token_id)

    def forgot_password(self, email: str) -> ForgotPasswordResponse:
        # Do not reveal whether the email exists.
        _ = self._users.find_by_email(email)
        return ForgotPasswordResponse(
            message=(
                "If an account exists for that email, we've sent password reset instructions."
            )
        )

    def social_login_stub(self, provider: str) -> AuthTokenResponse:
        provider_label = provider.capitalize()
        token, _token_id = create_access_token(f"social-{provider}")
        return AuthTokenResponse(
            token=token,
            user=AuthUser(
                id=f"social-{provider}",
                email=f"{provider}@discipline.os",
                name=f"{provider_label} User",
            ),
        )

    def _decode_active_token(self, token: str, allow_revoked: bool = False) -> dict:
        from app.core.security import decode_access_token

        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise ValueError("INVALID_TOKEN")

        token_id = payload.get("jti")
        if not allow_revoked and token_id in self._revoked_tokens:
            raise ValueError("INVALID_TOKEN")

        return payload

    @staticmethod
    def _build_auth_response(token: str, user: UserInDB) -> AuthTokenResponse:
        return AuthTokenResponse(
            token=token,
            user=AuthUser(**user.to_public()),
        )
