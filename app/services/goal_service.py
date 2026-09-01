from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import (
    GoalCreateRequest,
    GoalTaskCreateRequest,
    GoalTaskUpdateRequest,
    GoalUpdateRequest,
)


class GoalService:
    def __init__(self, repository: GoalRepository) -> None:
        self._repository = repository

    def list_goals(self, user_id: str) -> list[dict]:
        return self._repository.list_by_user(user_id)

    def get_goal(self, user_id: str, goal_id: str) -> dict | None:
        return self._repository.find_by_id(user_id, goal_id)

    def create_goal(self, user_id: str, payload: GoalCreateRequest) -> dict:
        return self._repository.create(
            user_id,
            {
                "title": payload.title,
                "description": payload.description,
                "why": payload.why,
                "deadline": payload.deadline,
                "category": payload.category,
                "priority": payload.priority,
            },
        )

    def update_goal(
        self, user_id: str, goal_id: str, payload: GoalUpdateRequest
    ) -> dict | None:
        data = payload.model_dump(exclude_unset=True, by_alias=False)
        return self._repository.update(user_id, goal_id, data)

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        return self._repository.archive(user_id, goal_id)

    def create_task(
        self, user_id: str, goal_id: str, payload: GoalTaskCreateRequest
    ) -> dict | None:
        return self._repository.create_task(
            user_id,
            goal_id,
            {"title": payload.title, "description": payload.description},
        )

    def update_task(
        self,
        user_id: str,
        goal_id: str,
        task_id: str,
        payload: GoalTaskUpdateRequest,
    ) -> dict | None:
        data = payload.model_dump(exclude_unset=True, by_alias=False)
        return self._repository.update_task(user_id, goal_id, task_id, data)

    def delete_task(self, user_id: str, goal_id: str, task_id: str) -> bool:
        return self._repository.delete_task(user_id, goal_id, task_id)

    def list_goals_for_sharing(self, user_id: str) -> list[dict]:
        return self._repository.list_goals_with_tasks_for_user(user_id)
