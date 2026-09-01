from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.repositories.share_comment_repository import ShareCommentRepository
from app.repositories.share_repository import ShareRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthUser
from app.schemas.common import error_response, success_response
from app.schemas.share import ReciprocalShareRequest, ShareCreateRequest, ShareUpdateRequest
from app.schemas.share_comment import ShareCommentCreateRequest
from app.services.share_service import ShareService

router = APIRouter()


def get_share_repository() -> ShareRepository:
    return ShareRepository()


def get_share_service(
    share_repository: Annotated[ShareRepository, Depends(get_share_repository)],
) -> ShareService:
    return ShareService(
        share_repository,
        TaskRepository(),
        UserRepository(),
        ShareCommentRepository(),
    )


@router.get("/incoming")
def list_incoming_shares(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    return success_response(
        service.list_incoming_shares(current_user.id, current_user.email)
    )


@router.get("/incoming/{share_id}")
def get_incoming_share(
    share_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    share = service.get_incoming_share(share_id, current_user.id, current_user.email)
    return success_response(share)


@router.get("/incoming/{share_id}/comments")
def list_share_comments(
    share_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    comments = service.list_share_comments(
        share_id, current_user.id, current_user.email
    )
    return success_response(comments)


@router.post("/incoming/{share_id}/comments")
def create_share_comment(
    share_id: str,
    body: ShareCommentCreateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    comment = service.create_share_comment(
        share_id,
        current_user.id,
        current_user.email,
        current_user.name,
        body,
    )
    return success_response(comment, "Comment posted", status_code=201)


@router.get("/incoming/{share_id}/data")
def get_incoming_share_data(
    share_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    payload = service.get_incoming_share_data(
        share_id, current_user.id, current_user.email
    )
    return success_response(payload)


@router.get("")
def list_shares(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    return success_response(service.list_shares(current_user.id))


@router.post("")
def create_share(
    body: ShareCreateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    result = service.create_share(current_user.id, body)
    return success_response(result, "Share created", status_code=201)


@router.get("/{share_id}/comments")
def list_outgoing_share_comments(
    share_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    comments = service.list_share_comments(
        share_id, current_user.id, current_user.email
    )
    return success_response(comments)


@router.post("/{share_id}/comments")
def create_outgoing_share_comment(
    share_id: str,
    body: ShareCommentCreateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    comment = service.create_share_comment(
        share_id,
        current_user.id,
        current_user.email,
        current_user.name,
        body,
    )
    return success_response(comment, "Comment posted", status_code=201)


@router.patch("/{share_id}")
def update_share(
    share_id: str,
    body: ShareUpdateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    updated = service.update_share(current_user.id, share_id, body)
    return success_response(updated, "Share updated")


@router.post("/incoming/{share_id}/reciprocal")
def respond_reciprocal_share(
    share_id: str,
    body: ReciprocalShareRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    result = service.respond_reciprocal_share(
        share_id, current_user.id, current_user.email, body
    )
    message = "Reciprocal share created" if result.get("accepted") else "Request dismissed"
    return success_response(result, message)


@router.delete("/{share_id}")
def revoke_share(
    share_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    revoked = service.revoke_share(current_user.id, share_id)
    if not revoked:
        return error_response("Share not found.", status_code=404, code="NOT_FOUND")
    return success_response(None, "Share revoked")


@router.get("/access/{token}")
def get_share_preview(
    token: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    preview = service.get_share_preview(token, current_user.email)
    return success_response(preview)


@router.get("/access/{token}/data")
def get_shared_data(
    token: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[ShareService, Depends(get_share_service)],
):
    payload = service.get_shared_data(token, current_user.email)
    return success_response(payload)
