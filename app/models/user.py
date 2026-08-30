from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserInDB(BaseModel):
    id: str
    email: EmailStr
    name: str
    password_hash: str
    joined_at: datetime
    is_active: bool = True

    @classmethod
    def from_document(cls, document: dict) -> "UserInDB":
        return cls(
            id=str(document["_id"]),
            email=document["email"],
            name=document["name"],
            password_hash=document["password_hash"],
            joined_at=document["joined_at"],
            is_active=document.get("is_active", True),
        )

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
        }
