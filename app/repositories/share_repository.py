from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from app.core.database import get_database
from app.utils.datetime import ensure_utc

TOKEN_HASH_INDEX = "token_hash_unique"


class ShareRepository:
    def __init__(self) -> None:
        self._collection: Collection = get_database()["shares"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("owner_id", 1), ("created_at", -1)])
        self._collection.create_index([("recipient_email", 1), ("status", 1)])
        self._collection.create_index([("recipient_user_id", 1), ("status", 1)])
        self._ensure_token_hash_index()

    def _ensure_token_hash_index(self) -> None:
        desired = {
            "key": [("token_hash", 1)],
            "unique": True,
            "sparse": True,
            "name": TOKEN_HASH_INDEX,
        }

        existing = self._collection.index_information()
        current = existing.get(TOKEN_HASH_INDEX) or existing.get("token_hash_1")

        if current:
            current_sparse = current.get("sparse", False)
            current_unique = current.get("unique", False)
            if current_unique and current_sparse:
                return
            # Drop legacy/conflicting index so we can recreate with sparse unique.
            legacy_name = TOKEN_HASH_INDEX if TOKEN_HASH_INDEX in existing else "token_hash_1"
            self._collection.drop_index(legacy_name)

        try:
            self._collection.create_index(
                desired["key"],
                unique=True,
                sparse=True,
                name=TOKEN_HASH_INDEX,
            )
        except OperationFailure as exc:
            if exc.code != 86:
                raise
            if "token_hash_1" in self._collection.index_information():
                self._collection.drop_index("token_hash_1")
            self._collection.create_index(
                desired["key"],
                unique=True,
                sparse=True,
                name=TOKEN_HASH_INDEX,
            )

    def list_by_owner(self, owner_id: str) -> list[dict]:
        cursor = self._collection.find({"owner_id": owner_id}).sort("created_at", -1)
        return [self._to_api_dict(doc) for doc in cursor]

    def list_by_recipient(self, recipient_email: str) -> list[dict]:
        cursor = self._collection.find(
            {
                "recipient_email": recipient_email.lower(),
                "status": "active",
            }
        ).sort("created_at", -1)
        now = datetime.now(UTC)
        results: list[dict] = []
        for doc in cursor:
            expires_at = doc.get("expires_at")
            if expires_at and ensure_utc(expires_at) < now:
                continue
            results.append(self._to_incoming_dict(doc))
        return results

    def find_by_id(self, owner_id: str, share_id: str) -> dict | None:
        doc = self._find_raw(owner_id, share_id)
        return self._to_api_dict(doc) if doc else None

    def find_for_recipient(self, share_id: str, recipient_email: str) -> dict | None:
        doc = self._find_raw_for_recipient(share_id, recipient_email)
        return doc

    def find_by_token_hash(self, token_hash: str) -> dict | None:
        return self._collection.find_one({"token_hash": token_hash})

    def create(
        self,
        owner_id: str,
        *,
        owner_name: str,
        owner_email: str,
        recipient_email: str,
        resources: list[dict],
        token_hash: str | None,
        expires_at: datetime | None,
    ) -> dict:
        now = datetime.now(UTC)
        document = {
            "owner_id": owner_id,
            "owner_name": owner_name.strip(),
            "owner_email": owner_email.lower(),
            "recipient_email": recipient_email.lower(),
            "recipient_user_id": None,
            "resources": resources,
            "token_hash": token_hash,
            "status": "active",
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection.insert_one(document)
        document["_id"] = result.inserted_id
        return self._to_api_dict(document)

    def revoke(self, owner_id: str, share_id: str) -> bool:
        doc = self._find_raw(owner_id, share_id)
        if not doc:
            return False
        self._collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "revoked", "updated_at": datetime.now(UTC)}},
        )
        return True

    def link_recipient_user(self, recipient_email: str, recipient_user_id: str) -> None:
        self._collection.update_many(
            {
                "recipient_email": recipient_email.lower(),
                "recipient_user_id": None,
            },
            {
                "$set": {
                    "recipient_user_id": recipient_user_id,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    def _find_raw(self, owner_id: str, share_id: str) -> dict | None:
        try:
            oid = ObjectId(share_id)
        except InvalidId:
            return None
        return self._collection.find_one({"_id": oid, "owner_id": owner_id})

    def _find_raw_for_recipient(self, share_id: str, recipient_email: str) -> dict | None:
        try:
            oid = ObjectId(share_id)
        except InvalidId:
            return None
        return self._collection.find_one(
            {
                "_id": oid,
                "recipient_email": recipient_email.lower(),
                "status": "active",
            }
        )

    def _to_api_dict(self, doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "ownerId": doc["owner_id"],
            "ownerName": doc.get("owner_name") or "Discipline OS user",
            "ownerEmail": doc.get("owner_email"),
            "recipientEmail": doc["recipient_email"],
            "resources": self._resources_api(doc),
            "status": doc.get("status", "active"),
            "expiresAt": doc["expires_at"].isoformat() if doc.get("expires_at") else None,
            "createdAt": doc["created_at"].isoformat(),
            "updatedAt": doc["updated_at"].isoformat(),
        }

    def _to_incoming_dict(self, doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "ownerId": doc["owner_id"],
            "ownerName": doc.get("owner_name") or "Discipline OS user",
            "ownerEmail": doc.get("owner_email"),
            "resources": self._resources_api(doc),
            "status": doc.get("status", "active"),
            "expiresAt": doc["expires_at"].isoformat() if doc.get("expires_at") else None,
            "createdAt": doc["created_at"].isoformat(),
            "updatedAt": doc["updated_at"].isoformat(),
        }

    @staticmethod
    def _resources_api(doc: dict) -> list[dict]:
        return [
            {
                "name": resource.get("name"),
                "permission": resource.get("permission", "view"),
            }
            for resource in doc.get("resources", [])
        ]
