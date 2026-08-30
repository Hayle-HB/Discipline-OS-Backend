from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection

from app.core.database import get_database

DEFAULT_ROUTINES = [
    {
        "name": "Morning Routine",
        "description": "Start the day with intention",
        "steps": [
            {"id": "s1", "label": "Make bed", "completed": False},
            {"id": "s2", "label": "Hydrate", "completed": False},
            {"id": "s3", "label": "Workout", "completed": False},
            {"id": "s4", "label": "Shower", "completed": False},
            {"id": "s5", "label": "Plan the day", "completed": False},
        ],
    },
    {
        "name": "Evening Wind-down",
        "description": "Prepare for restful sleep",
        "steps": [
            {"id": "s6", "label": "No screens after 9pm", "completed": False},
            {"id": "s7", "label": "Journal", "completed": False},
            {"id": "s8", "label": "Read fiction", "completed": False},
        ],
    },
]


class RoutineRepository:
    def __init__(self) -> None:
        self._collection: Collection = get_database()["routines"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("user_id", 1)])

    def list_by_user(self, user_id: str) -> list[dict]:
        count = self._collection.count_documents({"user_id": user_id})
        if count == 0:
            self._seed_defaults(user_id)

        docs = self._collection.find({"user_id": user_id}).sort("created_at", 1)
        return [self._to_api_dict(doc) for doc in docs]

    def toggle_step(self, user_id: str, routine_id: str, step_id: str) -> dict | None:
        doc = self._find_raw(user_id, routine_id)
        if not doc:
            return None

        steps = doc.get("steps", [])
        found = False
        for step in steps:
            if step.get("id") == step_id:
                step["completed"] = not step.get("completed", False)
                found = True
                break

        if not found:
            return None

        completed_today = len(steps) > 0 and all(s.get("completed") for s in steps)
        self._collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "steps": steps,
                    "completed_today": completed_today,
                    "updated_at": datetime.now(UTC),
                }
            },
        )
        refreshed = self._find_raw(user_id, routine_id)
        return self._to_api_dict(refreshed) if refreshed else None

    def _seed_defaults(self, user_id: str) -> None:
        now = datetime.now(UTC)
        for template in DEFAULT_ROUTINES:
            self._collection.insert_one(
                {
                    "user_id": user_id,
                    "name": template["name"],
                    "description": template["description"],
                    "steps": [dict(step) for step in template["steps"]],
                    "completed_today": False,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    def _find_raw(self, user_id: str, routine_id: str) -> dict | None:
        try:
            oid = ObjectId(routine_id)
        except InvalidId:
            return None
        return self._collection.find_one({"_id": oid, "user_id": user_id})

    @staticmethod
    def _to_api_dict(doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "userId": doc["user_id"],
            "name": doc["name"],
            "description": doc.get("description", ""),
            "steps": [
                {
                    "id": step["id"],
                    "label": step["label"],
                    "completed": bool(step.get("completed", False)),
                }
                for step in doc.get("steps", [])
            ],
            "completedToday": bool(doc.get("completed_today", False)),
        }
