from pydantic import BaseModel, ConfigDict, EmailStr, Field


VALID_SHARE_RESOURCES = frozenset(
    {
        "calendar",
        "tasks",
        "habits",
        "streak",
        "discipline_score",
        "analytics",
        "goals",
    }
)


class ShareResourcePermission(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    permission: str = "view"


class ShareResourceInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    permission: str = "view"


class ShareCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient_email: EmailStr = Field(alias="recipientEmail")
    resources: list[ShareResourceInput] = Field(min_length=1)
    expires_in_days: int | None = Field(default=None, alias="expiresInDays", ge=1, le=365)
    request_reciprocal_access: bool = Field(default=False, alias="requestReciprocalAccess")


class ShareUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    resources: list[ShareResourceInput] = Field(min_length=1)
    expires_in_days: int | None = Field(default=None, alias="expiresInDays", ge=1, le=365)


class ReciprocalShareRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    resources: list[ShareResourceInput] = Field(default_factory=list)
    accept: bool = True


class ShareResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    owner_id: str = Field(alias="ownerId")
    owner_name: str = Field(alias="ownerName")
    owner_email: str | None = Field(default=None, alias="ownerEmail")
    recipient_email: str = Field(alias="recipientEmail")
    resources: list[ShareResourcePermission]
    status: str
    expires_at: str | None = Field(default=None, alias="expiresAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    request_reciprocal_access: bool = Field(default=False, alias="requestReciprocalAccess")
    reciprocal_responded: bool = Field(default=False, alias="reciprocalResponded")


class IncomingShareSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    owner_id: str = Field(alias="ownerId")
    owner_name: str = Field(alias="ownerName")
    owner_email: str | None = Field(default=None, alias="ownerEmail")
    resources: list[ShareResourcePermission]
    status: str
    expires_at: str | None = Field(default=None, alias="expiresAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    reciprocal_pending: bool = Field(default=False, alias="reciprocalPending")


class ShareCreateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    share: ShareResponse
    share_token: str | None = Field(default=None, alias="shareToken")
    share_path: str | None = Field(default=None, alias="sharePath")
