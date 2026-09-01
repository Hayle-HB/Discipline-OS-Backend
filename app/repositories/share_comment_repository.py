from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection

from app.core.database import get_database


def make_thread_key(user_a_id: str, user_b_id: str) -> str:
    ordered = sorted([user_a_id, user_b_id])
    return f"{ordered[0]}:{ordered[1]}"


class ShareCommentRepository:
    def __init__(self) -> None:
        self._collection: Collection = get_database()["share_comments"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("thread_key", 1), ("created_at", 1)])
        self._collection.create_index([("parent_id", 1)])

    def list_by_thread(self, thread_key: str) -> list[dict]:
        cursor = self._collection.find({"thread_key": thread_key}).sort("created_at", 1)
        return [self._to_api_dict(doc) for doc in cursor]

    def create(
        self,
        *,
        thread_key: str,
        author_id: str,
        author_name: str,
        body: str,
        parent_id: str | None = None,
    ) -> dict:
        parent_oid = None
        if parent_id:
            try:
                parent_oid = ObjectId(parent_id)
            except InvalidId as exc:
                raise ValueError("Invalid parent comment.") from exc

            parent = self._collection.find_one(
                {"_id": parent_oid, "thread_key": thread_key}
            )
            if not parent:
                raise ValueError("Parent comment not found.")

        now = datetime.now(UTC)
        document = {
            "thread_key": thread_key,
            "author_id": author_id,
            "author_name": author_name.strip() or "Discipline OS user",
            "body": body.strip(),
            "parent_id": parent_oid,
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection.insert_one(document)
        document["_id"] = result.inserted_id
        return self._to_api_dict(document)

    @staticmethod
    def _to_api_dict(doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "threadKey": doc["thread_key"],
            "authorId": doc["author_id"],
            "authorName": doc.get("author_name") or "Discipline OS user",
            "body": doc["body"],
            "parentId": str(doc["parent_id"]) if doc.get("parent_id") else None,
            "createdAt": doc["created_at"].isoformat(),
            "updatedAt": doc["updated_at"].isoformat(),
        }
