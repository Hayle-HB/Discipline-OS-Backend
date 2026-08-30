from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.repositories.task_repository import TaskRepository
from app.schemas.auth import AuthUser
from app.schemas.common import success_response
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def get_task_repository() -> TaskRepository:
    return TaskRepository()


def get_analytics_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> AnalyticsService:
    return AnalyticsService(repository)


@router.get("")
def get_analytics(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
):
    return success_response(service.get_analytics(current_user.id))
