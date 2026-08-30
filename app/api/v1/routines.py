from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.repositories.routine_repository import RoutineRepository
from app.schemas.auth import AuthUser
from app.schemas.common import error_response, success_response
from app.schemas.routine import ToggleRoutineStepRequest
from app.services.routine_service import RoutineService

router = APIRouter()


def get_routine_repository() -> RoutineRepository:
    return RoutineRepository()


def get_routine_service(
    repository: Annotated[RoutineRepository, Depends(get_routine_repository)],
) -> RoutineService:
    return RoutineService(repository)


@router.get("")
def list_routines(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[RoutineService, Depends(get_routine_service)],
):
    return success_response(service.list_routines(current_user.id))


@router.patch("")
def toggle_routine_step(
    body: ToggleRoutineStepRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[RoutineService, Depends(get_routine_service)],
):
    if not body.routine_id or not body.step_id:
        return error_response(
            "routineId and stepId are required.",
            status_code=400,
            code="VALIDATION_ERROR",
        )

    routine = service.toggle_step(current_user.id, body.routine_id, body.step_id)
    if not routine:
        return error_response("Routine or step not found.", status_code=404, code="NOT_FOUND")
    return success_response(routine)
