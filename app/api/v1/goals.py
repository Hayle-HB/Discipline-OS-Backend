from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.repositories.goal_repository import GoalRepository
from app.schemas.auth import AuthUser
from app.schemas.common import error_response, success_response
from app.schemas.goal import (
    GoalCreateRequest,
    GoalTaskCreateRequest,
    GoalTaskUpdateRequest,
    GoalUpdateRequest,
)
from app.services.goal_service import GoalService

router = APIRouter()


def get_goal_repository() -> GoalRepository:
    return GoalRepository()


def get_goal_service(
    repository: Annotated[GoalRepository, Depends(get_goal_repository)],
) -> GoalService:
    return GoalService(repository)


@router.get("")
def list_goals(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    return success_response(service.list_goals(current_user.id))


@router.post("")
def create_goal(
    body: GoalCreateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    if not body.title.strip():
        return error_response("Goal title is required.", status_code=400, code="VALIDATION_ERROR")
    goal = service.create_goal(current_user.id, body)
    return success_response(goal, "Goal created", status_code=201)


@router.get("/{goal_id}")
def get_goal(
    goal_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    goal = service.get_goal(current_user.id, goal_id)
    if not goal:
        return error_response("Goal not found.", status_code=404, code="NOT_FOUND")
    return success_response(goal)


@router.patch("/{goal_id}")
def update_goal(
    goal_id: str,
    body: GoalUpdateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    goal = service.update_goal(current_user.id, goal_id, body)
    if not goal:
        return error_response("Goal not found.", status_code=404, code="NOT_FOUND")
    return success_response(goal, "Goal updated")


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    if not service.delete_goal(current_user.id, goal_id):
        return error_response("Goal not found.", status_code=404, code="NOT_FOUND")
    return success_response(None, "Goal deleted")


@router.post("/{goal_id}/tasks")
def create_goal_task(
    goal_id: str,
    body: GoalTaskCreateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    if not body.title.strip():
        return error_response("Task title is required.", status_code=400, code="VALIDATION_ERROR")
    task = service.create_task(current_user.id, goal_id, body)
    if not task:
        return error_response("Goal not found.", status_code=404, code="NOT_FOUND")
    return success_response(task, "Task added", status_code=201)


@router.patch("/{goal_id}/tasks/{task_id}")
def update_goal_task(
    goal_id: str,
    task_id: str,
    body: GoalTaskUpdateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    task = service.update_task(current_user.id, goal_id, task_id, body)
    if not task:
        return error_response("Task not found.", status_code=404, code="NOT_FOUND")
    return success_response(task, "Task updated")


@router.delete("/{goal_id}/tasks/{task_id}")
def delete_goal_task(
    goal_id: str,
    task_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[GoalService, Depends(get_goal_service)],
):
    if not service.delete_task(current_user.id, goal_id, task_id):
        return error_response("Task not found.", status_code=404, code="NOT_FOUND")
    return success_response(None, "Task deleted")
