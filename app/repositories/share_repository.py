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
        cursor = self._collection.find(
            {"owner_id": owner_id, "status": "active"}
        ).sort("updated_at", -1)
        grouped: dict[str, dict] = {}
        for doc in cursor:
            key = doc["recipient_email"].lower()
            if key not in grouped:
                grouped[key] = doc
                continue
            grouped[key] = self._merge_share_docs(grouped[key], doc)
        return [self._to_api_dict(doc) for doc in grouped.values()]

    def list_by_recipient(self, recipient_email: str) -> list[dict]:
        cursor = self._collection.find(
            {
                "recipient_email": recipient_email.lower(),
                "status": "active",
            }
        ).sort("updated_at", -1)
        now = datetime.now(UTC)
        grouped: dict[str, dict] = {}
        for doc in cursor:
            expires_at = doc.get("expires_at")
            if expires_at and ensure_utc(expires_at) < now:
                continue
            key = doc["owner_id"]
            if key not in grouped:
                grouped[key] = doc
                continue
            grouped[key] = self._merge_share_docs(grouped[key], doc)
        return [self._to_incoming_dict(doc) for doc in grouped.values()]

    def find_by_id(self, owner_id: str, share_id: str) -> dict | None:
        doc = self._find_raw(owner_id, share_id)
        return self._to_api_dict(doc) if doc else None

    def find_for_recipient(self, share_id: str, recipient_email: str) -> dict | None:
        doc = self._find_raw_for_recipient(share_id, recipient_email)
        return doc

    def find_by_token_hash(self, token_hash: str) -> dict | None:
        return self._collection.find_one({"token_hash": token_hash})

    def find_active_by_pair(self, owner_id: str, recipient_email: str) -> dict | None:
        return self._collection.find_one(
            {
                "owner_id": owner_id,
                "recipient_email": recipient_email.lower(),
                "status": "active",
            }
        )

    def has_active_share_to(self, owner_id: str, recipient_email: str) -> bool:
        return self.find_active_by_pair(owner_id, recipient_email) is not None

    def users_have_active_relationship(
        self,
        user_a_id: str,
        user_a_email: str,
        user_b_id: str,
        user_b_email: str,
    ) -> bool:
        b_email = user_b_email.lower()
        a_email = user_a_email.lower()
        if self.find_active_by_pair(user_a_id, b_email):
            return True
        return self.find_active_by_pair(user_b_id, a_email) is not None

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
        reciprocal_requested: bool = False,
    ) -> dict:
        existing = self.find_active_by_pair(owner_id, recipient_email)
        if existing:
            return self._update_existing_share(
                existing,
                owner_name=owner_name,
                owner_email=owner_email,
                resources=resources,
                expires_at=expires_at,
                reciprocal_requested=reciprocal_requested,
            )

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
            "reciprocal_requested": reciprocal_requested,
            "reciprocal_responded": False,
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection.insert_one(document)
        document["_id"] = result.inserted_id
        return self._to_api_dict(document)

    def update_share(
        self,
        owner_id: str,
        share_id: str,
        *,
        resources: list[dict],
        expires_at: datetime | None = None,
        update_expiration: bool = False,
    ) -> dict | None:
        doc = self._find_raw(owner_id, share_id)
        if not doc or doc.get("status") != "active":
            return None

        updates: dict = {
            "resources": resources,
            "updated_at": datetime.now(UTC),
        }
        if update_expiration:
            updates["expires_at"] = expires_at

        self._collection.update_one({"_id": doc["_id"]}, {"$set": updates})
        self._revoke_duplicate_active_shares(
            owner_id,
            doc["recipient_email"],
            keep_id=doc["_id"],
        )
        updated = self._collection.find_one({"_id": doc["_id"]})
        return self._to_api_dict(updated) if updated else None

    def mark_reciprocal_responded(self, share_id: str) -> None:
        try:
            oid = ObjectId(share_id)
        except InvalidId:
            return
        self._collection.update_one(
            {"_id": oid},
            {
                "$set": {
                    "reciprocal_responded": True,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

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
            "requestReciprocalAccess": bool(doc.get("reciprocal_requested")),
            "reciprocalResponded": bool(doc.get("reciprocal_responded")),
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
            "reciprocalPending": bool(
                doc.get("reciprocal_requested") and not doc.get("reciprocal_responded")
            ),
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

    @staticmethod
    def _merge_resources(
        left: list[dict], right: list[dict]
    ) -> list[dict]:
        merged: dict[str, dict] = {}
        for resource in [*left, *right]:
            name = resource.get("name")
            if name:
                merged[name] = {
                    "name": name,
                    "permission": resource.get("permission", "view"),
                }
        return list(merged.values())

    def _merge_share_docs(self, primary: dict, secondary: dict) -> dict:
        merged = dict(primary)
        merged["resources"] = self._merge_resources(
            primary.get("resources", []),
            secondary.get("resources", []),
        )
        merged["reciprocal_requested"] = bool(
            primary.get("reciprocal_requested") or secondary.get("reciprocal_requested")
        )
        merged["reciprocal_responded"] = bool(
            primary.get("reciprocal_responded") or secondary.get("reciprocal_responded")
        )
        primary_updated = primary.get("updated_at")
        secondary_updated = secondary.get("updated_at")
        if secondary_updated and (
            not primary_updated or secondary_updated > primary_updated
        ):
            merged["_id"] = secondary["_id"]
            merged["updated_at"] = secondary_updated
        return merged

    def _update_existing_share(
        self,
        existing: dict,
        *,
        owner_name: str,
        owner_email: str,
        resources: list[dict],
        expires_at: datetime | None,
        reciprocal_requested: bool,
    ) -> dict:
        now = datetime.now(UTC)
        merged_resources = resources
        updates: dict = {
            "owner_name": owner_name.strip(),
            "owner_email": owner_email.lower(),
            "resources": merged_resources,
            "updated_at": now,
            "status": "active",
        }
        if expires_at is not None:
            updates["expires_at"] = expires_at
        if reciprocal_requested:
            updates["reciprocal_requested"] = True

        self._collection.update_one({"_id": existing["_id"]}, {"$set": updates})
        self._revoke_duplicate_active_shares(
            existing["owner_id"],
            existing["recipient_email"],
            keep_id=existing["_id"],
        )
        updated = self._collection.find_one({"_id": existing["_id"]})
        return self._to_api_dict(updated) if updated else self._to_api_dict(existing)

    def _revoke_duplicate_active_shares(
        self,
        owner_id: str,
        recipient_email: str,
        *,
        keep_id: ObjectId,
    ) -> None:
        now = datetime.now(UTC)
        self._collection.update_many(
            {
                "owner_id": owner_id,
                "recipient_email": recipient_email.lower(),
                "status": "active",
                "_id": {"$ne": keep_id},
            },
            {"$set": {"status": "revoked", "updated_at": now}},
        )
