from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection

from app.core.database import get_database
from app.utils.periods import (
    get_period_log_key,
    normalize_completion_log,
    normalize_task_fields,
    parse_date_key,
    today_key,
)

VALID_PERIODS = {"daily", "weekly", "monthly", "yearly"}
VALID_PRIORITIES = {"low", "medium", "high"}


class TaskRepository:
    def __init__(self) -> None:
        self._collection: Collection = get_database()["tasks"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("user_id", 1), ("status", 1), ("period", 1)])
        self._collection.create_index([("user_id", 1), ("created_at", -1)])

    def list_by_user(self, user_id: str) -> list[dict]:
        docs = self._collection.find(
            {"user_id": user_id, "status": {"$ne": "archived"}}
        ).sort([("sort_order", 1), ("created_at", -1)])
        return [self._to_api_dict(doc) for doc in docs]

    def find_by_id(self, user_id: str, task_id: str) -> dict | None:
        doc = self._find_raw(user_id, task_id)
        return self._to_api_dict(doc) if doc else None

    def create(self, user_id: str, data: dict) -> dict:
        now = datetime.now(UTC)
        period = data["period"]
        if period not in VALID_PERIODS:
            raise ValueError("INVALID_PERIOD")

        priority = data.get("priority") or "medium"
        if priority not in VALID_PRIORITIES:
            priority = "medium"

        document = {
            "user_id": user_id,
            "label": data["label"].strip(),
            "description": data.get("description") or None,
            "period": period,
            "category": data.get("category") or "general",
            "priority": priority,
            "preferred_time": data.get("preferred_time") or None,
            "estimated_minutes": data.get("estimated_minutes"),
            "status": "active",
            "sort_order": 0,
            "completion_log": {},
            "longest_streak": 0,
            "created_at": now,
            "updated_at": now,
        }
        completed, streak = normalize_task_fields(period, {})
        document["completed"] = completed
        document["streak"] = streak

        result = self._collection.insert_one(document)
        document["_id"] = result.inserted_id
        return self._to_api_dict(document)

    def update(self, user_id: str, task_id: str, data: dict) -> dict | None:
        doc = self._find_raw(user_id, task_id)
        if not doc:
            return None

        updates: dict = {"updated_at": datetime.now(UTC)}

        if "label" in data and data["label"] is not None:
            updates["label"] = data["label"].strip()
        if "description" in data:
            updates["description"] = data["description"] or None
        if "category" in data and data["category"] is not None:
            updates["category"] = data["category"]
        if "preferred_time" in data:
            updates["preferred_time"] = data["preferred_time"] or None
        if "estimated_minutes" in data:
            updates["estimated_minutes"] = data["estimated_minutes"]
        if "priority" in data and data["priority"] is not None:
            priority = data["priority"]
            updates["priority"] = priority if priority in VALID_PRIORITIES else "medium"
        if "period" in data and data["period"] is not None:
            if data["period"] not in VALID_PERIODS:
                raise ValueError("INVALID_PERIOD")
            updates["period"] = data["period"]

        self._collection.update_one({"_id": doc["_id"]}, {"$set": updates})
        refreshed = self._find_raw(user_id, task_id)
        return self._to_api_dict(refreshed) if refreshed else None

    def record_completion(
        self,
        user_id: str,
        task_id: str,
        status: str,
        date_key: str | None = None,
    ) -> dict | None:
        doc = self._find_raw(user_id, task_id)
        if not doc:
            return None

        if status not in {"done", "missed"}:
            raise ValueError("INVALID_STATUS")

        ref_date = parse_date_key(date_key or today_key())
        period = doc["period"]
        period_key = get_period_log_key(ref_date, period)
        log = normalize_completion_log(doc.get("completion_log"))
        previous = log.get(period_key)

        if previous and previous.get("status") == status:
            refreshed = self._find_raw(user_id, task_id)
            return self._to_api_dict(refreshed) if refreshed else None

        if status == "done":
            entry = {
                "status": "done",
                "completed_at": datetime.now(UTC).isoformat(),
            }
            if doc.get("estimated_minutes") is not None:
                entry["duration_minutes"] = doc["estimated_minutes"]
            log[period_key] = entry
        else:
            log[period_key] = {"status": "missed"}

        completed, streak = normalize_task_fields(period, log, ref_date)
        longest = max(doc.get("longest_streak", 0), streak)

        self._collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "completion_log": log,
                    "completed": completed,
                    "streak": streak,
                    "longest_streak": longest,
                    "updated_at": datetime.now(UTC),
                }
            },
        )
        refreshed = self._find_raw(user_id, task_id)
        return self._to_api_dict(refreshed) if refreshed else None

    def delete(self, user_id: str, task_id: str) -> bool:
        doc = self._find_raw(user_id, task_id)
        if not doc:
            return False
        self._collection.delete_one({"_id": doc["_id"]})
        return True

    def _find_raw(self, user_id: str, task_id: str) -> dict | None:
        try:
            oid = ObjectId(task_id)
        except InvalidId:
            return None
        return self._collection.find_one({"_id": oid, "user_id": user_id})

    @staticmethod
    def _to_api_dict(doc: dict) -> dict:
        log = normalize_completion_log(doc.get("completion_log"))
        api_log: dict = {}
        for key, entry in log.items():
            api_entry: dict = {"status": entry.get("status", "missed")}
            if entry.get("completed_at"):
                api_entry["completedAt"] = entry["completed_at"]
            elif entry.get("completedAt"):
                api_entry["completedAt"] = entry["completedAt"]
            duration = entry.get("duration_minutes", entry.get("durationMinutes"))
            if duration is not None:
                api_entry["durationMinutes"] = duration
            if entry.get("note"):
                api_entry["note"] = entry["note"]
            api_log[key] = api_entry

        created = doc.get("created_at")
        return {
            "id": str(doc["_id"]),
            "userId": doc["user_id"],
            "label": doc["label"],
            "description": doc.get("description"),
            "period": doc["period"],
            "completed": bool(doc.get("completed", False)),
            "streak": int(doc.get("streak", 0)),
            "category": doc.get("category", "general"),
            "priority": doc.get("priority", "medium"),
            "preferredTime": doc.get("preferred_time"),
            "estimatedMinutes": doc.get("estimated_minutes"),
            "createdAt": created.isoformat() if hasattr(created, "isoformat") else str(created),
            "completionLog": api_log or None,
        }
