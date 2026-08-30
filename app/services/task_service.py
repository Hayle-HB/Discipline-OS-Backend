from app.repositories.routine_repository import RoutineRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import (
    TaskCreateRequest,
    TaskUpdateRequest,
)
from app.services.analytics_service import build_analytics


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self._tasks = repository
        self._routines = RoutineRepository()

    def get_dashboard(self, user_id: str) -> dict:
        tasks = self._tasks.list_by_user(user_id)
        by_period = self._group_by_period(tasks)
        stats = self._compute_stats(tasks)
        analytics = build_analytics(tasks)
        return {
            "tasks": tasks,
            "tasksByPeriod": by_period,
            "stats": stats,
            "weeklyActivity": analytics["weeklyActivity"],
            "routines": self._routines.list_by_user(user_id),
        }

    def create_task(self, user_id: str, payload: TaskCreateRequest) -> dict:
        return self._tasks.create(
            user_id,
            {
                "label": payload.label,
                "period": payload.period,
                "category": payload.category,
                "description": payload.description,
                "priority": payload.priority,
                "preferred_time": payload.preferred_time,
                "estimated_minutes": payload.estimated_minutes,
            },
        )

    def update_task(self, user_id: str, task_id: str, payload: TaskUpdateRequest) -> dict | None:
        data = payload.model_dump(exclude_unset=True, by_alias=False)
        if not data:
            return self._tasks.find_by_id(user_id, task_id)
        return self._tasks.update(user_id, task_id, data)

    def record_completion(
        self,
        user_id: str,
        task_id: str,
        status: str,
        date_key: str | None,
    ) -> dict | None:
        return self._tasks.record_completion(user_id, task_id, status, date_key)

    def delete_task(self, user_id: str, task_id: str) -> bool:
        return self._tasks.delete(user_id, task_id)

    @staticmethod
    def _group_by_period(tasks: list[dict]) -> dict:
        grouped: dict[str, list] = {
            "daily": [],
            "weekly": [],
            "monthly": [],
            "yearly": [],
        }
        for task in tasks:
            period = task.get("period", "daily")
            if period in grouped:
                grouped[period].append(task)
        return grouped

    @staticmethod
    def _compute_stats(tasks: list[dict]) -> dict:
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("completed"))
        best_streak = max((t.get("streak", 0) for t in tasks), default=0)
        score = round((completed / total) * 100) if total else 0
        return {
            "completed": completed,
            "total": total,
            "bestStreak": best_streak,
            "score": score,
            "progress": score,
        }
