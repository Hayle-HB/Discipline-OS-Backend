from datetime import UTC, date, datetime

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection

from app.core.database import get_database
from app.schemas.goal import VALID_GOAL_CATEGORIES, VALID_GOAL_PRIORITIES


class GoalRepository:
    def __init__(self) -> None:
        self._goals: Collection = get_database()["goals"]
        self._tasks: Collection = get_database()["goal_tasks"]

    def ensure_indexes(self) -> None:
        self._goals.create_index([("user_id", 1), ("status", 1), ("created_at", -1)])
        self._tasks.create_index([("goal_id", 1), ("user_id", 1), ("sort_order", 1)])

    def list_by_user(self, user_id: str) -> list[dict]:
        docs = self._goals.find(
            {"user_id": user_id, "status": {"$ne": "archived"}}
        ).sort([("created_at", -1)])
        return [self._to_summary(doc, user_id) for doc in docs]

    def find_by_id(self, user_id: str, goal_id: str) -> dict | None:
        doc = self._find_raw_goal(user_id, goal_id)
        if not doc:
            return None
        return self._to_detail(doc, user_id)

    def create(self, user_id: str, data: dict) -> dict:
        now = datetime.now(UTC)
        category = data.get("category") or "personal"
        if category not in VALID_GOAL_CATEGORIES:
            category = "other"

        priority = data.get("priority") or "medium"
        if priority not in VALID_GOAL_PRIORITIES:
            priority = "medium"

        document = {
            "user_id": user_id,
            "title": data["title"].strip(),
            "description": (data.get("description") or "").strip() or None,
            "why": (data.get("why") or "").strip() or None,
            "deadline": self._normalize_deadline(data.get("deadline")),
            "category": category,
            "priority": priority,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        result = self._goals.insert_one(document)
        document["_id"] = result.inserted_id
        return self._to_detail(document, user_id)

    def update(self, user_id: str, goal_id: str, data: dict) -> dict | None:
        doc = self._find_raw_goal(user_id, goal_id)
        if not doc:
            return None

        updates: dict = {"updated_at": datetime.now(UTC)}

        if "title" in data and data["title"] is not None:
            updates["title"] = data["title"].strip()
        if "description" in data:
            updates["description"] = (data["description"] or "").strip() or None
        if "why" in data:
            updates["why"] = (data["why"] or "").strip() or None
        if "deadline" in data:
            updates["deadline"] = self._normalize_deadline(data["deadline"])
        if "category" in data and data["category"] is not None:
            category = data["category"]
            updates["category"] = category if category in VALID_GOAL_CATEGORIES else "other"
        if "priority" in data and data["priority"] is not None:
            priority = data["priority"]
            updates["priority"] = priority if priority in VALID_GOAL_PRIORITIES else "medium"

        self._goals.update_one({"_id": doc["_id"]}, {"$set": updates})
        updated = self._goals.find_one({"_id": doc["_id"]})
        return self._to_detail(updated, user_id) if updated else None

    def archive(self, user_id: str, goal_id: str) -> bool:
        doc = self._find_raw_goal(user_id, goal_id)
        if not doc:
            return False
        self._goals.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "archived", "updated_at": datetime.now(UTC)}},
        )
        return True

    def list_tasks(self, user_id: str, goal_id: str) -> list[dict]:
        if not self._find_raw_goal(user_id, goal_id):
            return []
        docs = self._tasks.find({"user_id": user_id, "goal_id": goal_id}).sort(
            [("sort_order", 1), ("created_at", 1)]
        )
        return [self._task_to_api(doc) for doc in docs]

    def create_task(self, user_id: str, goal_id: str, data: dict) -> dict | None:
        if not self._find_raw_goal(user_id, goal_id):
            return None

        now = datetime.now(UTC)
        sort_order = self._tasks.count_documents({"user_id": user_id, "goal_id": goal_id})
        document = {
            "user_id": user_id,
            "goal_id": goal_id,
            "title": data["title"].strip(),
            "description": (data.get("description") or "").strip() or None,
            "completed": False,
            "sort_order": sort_order,
            "created_at": now,
            "updated_at": now,
        }
        result = self._tasks.insert_one(document)
        document["_id"] = result.inserted_id
        self._goals.update_one(
            {"user_id": user_id, "_id": ObjectId(goal_id)},
            {"$set": {"updated_at": now}},
        )
        return self._task_to_api(document)

    def update_task(
        self, user_id: str, goal_id: str, task_id: str, data: dict
    ) -> dict | None:
        doc = self._find_raw_task(user_id, goal_id, task_id)
        if not doc:
            return None

        updates: dict = {"updated_at": datetime.now(UTC)}
        if "title" in data and data["title"] is not None:
            updates["title"] = data["title"].strip()
        if "description" in data:
            updates["description"] = (data["description"] or "").strip() or None
        if "completed" in data and data["completed"] is not None:
            updates["completed"] = bool(data["completed"])

        self._tasks.update_one({"_id": doc["_id"]}, {"$set": updates})
        self._goals.update_one(
            {"user_id": user_id, "_id": ObjectId(goal_id)},
            {"$set": {"updated_at": datetime.now(UTC)}},
        )
        updated = self._tasks.find_one({"_id": doc["_id"]})
        return self._task_to_api(updated) if updated else None

    def delete_task(self, user_id: str, goal_id: str, task_id: str) -> bool:
        doc = self._find_raw_task(user_id, goal_id, task_id)
        if not doc:
            return False
        self._tasks.delete_one({"_id": doc["_id"]})
        self._goals.update_one(
            {"user_id": user_id, "_id": ObjectId(goal_id)},
            {"$set": {"updated_at": datetime.now(UTC)}},
        )
        return True

    def list_goals_with_tasks_for_user(self, user_id: str) -> list[dict]:
        summaries = self.list_by_user(user_id)
        results: list[dict] = []
        for summary in summaries:
            goal_id = summary["id"]
            tasks = self.list_tasks(user_id, goal_id)
            detail = {**summary, "tasks": tasks}
            results.append(detail)
        return results

    def _find_raw_goal(self, user_id: str, goal_id: str) -> dict | None:
        try:
            oid = ObjectId(goal_id)
        except InvalidId:
            return None
        return self._goals.find_one(
            {"_id": oid, "user_id": user_id, "status": {"$ne": "archived"}}
        )

    def _find_raw_task(self, user_id: str, goal_id: str, task_id: str) -> dict | None:
        try:
            oid = ObjectId(task_id)
        except InvalidId:
            return None
        return self._tasks.find_one(
            {"_id": oid, "user_id": user_id, "goal_id": goal_id}
        )

    def _task_counts(self, user_id: str, goal_id: str) -> tuple[int, int]:
        total = self._tasks.count_documents({"user_id": user_id, "goal_id": goal_id})
        completed = self._tasks.count_documents(
            {"user_id": user_id, "goal_id": goal_id, "completed": True}
        )
        return total, completed

    def _to_summary(self, doc: dict, user_id: str) -> dict:
        goal_id = str(doc["_id"])
        total, completed = self._task_counts(user_id, goal_id)
        progress = round((completed / total) * 100) if total else 0
        return {
            "id": goal_id,
            "title": doc["title"],
            "description": doc.get("description"),
            "why": doc.get("why"),
            "deadline": doc.get("deadline"),
            "category": doc.get("category", "personal"),
            "priority": doc.get("priority", "medium"),
            "status": doc.get("status", "active"),
            "progressPercent": progress,
            "tasksTotal": total,
            "tasksCompleted": completed,
            "daysRemaining": self._days_remaining(doc.get("deadline")),
            "createdAt": doc["created_at"].isoformat(),
            "updatedAt": doc["updated_at"].isoformat(),
        }

    def _to_detail(self, doc: dict, user_id: str) -> dict:
        goal_id = str(doc["_id"])
        summary = self._to_summary(doc, user_id)
        tasks = self.list_tasks(user_id, goal_id)
        return {**summary, "tasks": tasks}

    @staticmethod
    def _task_to_api(doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "goalId": doc["goal_id"],
            "title": doc["title"],
            "description": doc.get("description"),
            "completed": bool(doc.get("completed")),
            "sortOrder": doc.get("sort_order", 0),
            "createdAt": doc["created_at"].isoformat(),
            "updatedAt": doc["updated_at"].isoformat(),
        }

    @staticmethod
    def _normalize_deadline(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            try:
                date.fromisoformat(cleaned[:10])
            except ValueError:
                return None
        return cleaned

    @staticmethod
    def _days_remaining(deadline: str | None) -> int | None:
        if not deadline:
            return None
        try:
            deadline_date = date.fromisoformat(deadline[:10])
        except ValueError:
            return None
        return (deadline_date - date.today()).days
