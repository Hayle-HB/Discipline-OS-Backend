from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.repositories.task_repository import TaskRepository
from app.schemas.auth import AuthUser
from app.schemas.common import error_response, success_response
from app.schemas.task import RecordCompletionRequest, TaskCreateRequest, TaskUpdateRequest
from app.services.task_service import TaskService

router = APIRouter()


def get_task_repository() -> TaskRepository:
    return TaskRepository()


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(repository)


@router.get("")
def list_tasks(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
):
    return success_response(service.get_dashboard(current_user.id))


@router.post("")
def create_task(
    body: TaskCreateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
):
    if not body.label.strip():
        return error_response("Task label is required.", status_code=400, code="VALIDATION_ERROR")
    if body.period not in {"daily", "weekly", "monthly", "yearly"}:
        return error_response(
            "Valid period is required (daily, weekly, monthly, yearly).",
            status_code=400,
            code="VALIDATION_ERROR",
        )
    try:
        task = service.create_task(current_user.id, body)
        return success_response(task, "Task added", status_code=201)
    except ValueError as exc:
        if str(exc) == "INVALID_PERIOD":
            return error_response("Invalid period.", status_code=400, code="VALIDATION_ERROR")
        raise


@router.patch("/{task_id}")
def record_completion(
    task_id: str,
    body: RecordCompletionRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
):
    if body.status not in {"done", "missed"}:
        return error_response(
            "Status must be 'done' or 'missed'.",
            status_code=400,
            code="VALIDATION_ERROR",
        )
    task = service.record_completion(
        current_user.id, task_id, body.status, body.date
    )
    if not task:
        return error_response("Task not found.", status_code=404, code="NOT_FOUND")
    return success_response(task)


@router.put("/{task_id}")
def update_task(
    task_id: str,
    body: TaskUpdateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
):
    if body.label is not None and not body.label.strip():
        return error_response("Task label cannot be empty.", status_code=400, code="VALIDATION_ERROR")
    if body.period is not None and body.period not in {"daily", "weekly", "monthly", "yearly"}:
        return error_response("Invalid period.", status_code=400, code="VALIDATION_ERROR")
    try:
        task = service.update_task(current_user.id, task_id, body)
    except ValueError as exc:
        if str(exc) == "INVALID_PERIOD":
            return error_response("Invalid period.", status_code=400, code="VALIDATION_ERROR")
        raise
    if not task:
        return error_response("Task not found.", status_code=404, code="NOT_FOUND")
    return success_response(task, "Task updated")


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
):
    deleted = service.delete_task(current_user.id, task_id)
    if not deleted:
        return error_response("Task not found.", status_code=404, code="NOT_FOUND")
    return success_response(None, "Task deleted")
