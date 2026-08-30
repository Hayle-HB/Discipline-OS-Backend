from app.repositories.routine_repository import RoutineRepository


class RoutineService:
    def __init__(self, repository: RoutineRepository) -> None:
        self._routines = repository

    def list_routines(self, user_id: str) -> list[dict]:
        return self._routines.list_by_user(user_id)

    def toggle_step(self, user_id: str, routine_id: str, step_id: str) -> dict | None:
        return self._routines.toggle_step(user_id, routine_id, step_id)
