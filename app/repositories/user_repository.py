from datetime import UTC, datetime

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.security import hash_password
from app.models.user import UserCreate, UserInDB


class UserRepository:
    def __init__(self) -> None:
        self._collection: Collection = get_database()["users"]

    def ensure_indexes(self) -> None:
        self._collection.create_index("email", unique=True)

    def find_by_email(self, email: str) -> UserInDB | None:
        document = self._collection.find_one({"email": email.lower()})
        return UserInDB.from_document(document) if document else None

    def find_by_id(self, user_id: str) -> UserInDB | None:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            document = self._collection.find_one({"_id": ObjectId(user_id)})
        except InvalidId:
            return None
        return UserInDB.from_document(document) if document else None

    def create(self, data: UserCreate) -> UserInDB:
        now = datetime.now(UTC)
        document = {
            "email": data.email.lower(),
            "name": data.name.strip(),
            "password_hash": hash_password(data.password),
            "joined_at": now,
            "is_active": True,
        }

        try:
            result = self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise ValueError("EMAIL_EXISTS") from exc

        document["_id"] = result.inserted_id
        return UserInDB.from_document(document)

    def seed_demo_user(self) -> None:
        if self.find_by_email("demo@discipline.os"):
            return

        self.create(
            UserCreate(
                name="Demo User",
                email="demo@discipline.os",
                password="password123",
            )
        )
