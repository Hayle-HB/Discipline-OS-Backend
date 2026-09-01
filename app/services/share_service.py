"""Selective progress sharing with resource-based authorization."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta
from urllib.parse import unquote

from app.core.exceptions import AppError
from app.repositories.share_repository import ShareRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.share import VALID_SHARE_RESOURCES, ShareCreateRequest
from app.services.analytics_service import build_analytics
from app.utils.datetime import ensure_utc
from app.utils.periods import normalize_completion_log, to_date_key


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _daily_tasks(tasks: list[dict]) -> list[dict]:
    return [task for task in tasks if task.get("period") == "daily"]


def _compute_day_metrics(daily_tasks: list[dict], date_key: str) -> dict:
    done = 0
    missed = 0
    for task in daily_tasks:
        log = normalize_completion_log(task.get("completionLog"))
        entry = log.get(date_key)
        if not entry:
            continue
        if entry.get("status") == "done":
            done += 1
        elif entry.get("status") == "missed":
            missed += 1
    total = len(daily_tasks)
    pending = total - done - missed
    rate = round((done / total) * 100) if total else 0
    return {
        "dateKey": date_key,
        "done": done,
        "missed": missed,
        "pending": pending,
        "total": total,
        "rate": rate,
    }


def _build_calendar_data(tasks: list[dict]) -> dict:
    daily = _daily_tasks(tasks)
    days = []
    for offset in range(89, -1, -1):
        day = date.today() - timedelta(days=offset)
        days.append(_compute_day_metrics(daily, to_date_key(day)))

    tracked = [day for day in days if day["done"] or day["missed"]]
    return {
        "days": days,
        "summary": {
            "daysTracked": len(tracked),
            "totalDone": sum(day["done"] for day in tracked),
            "totalMissed": sum(day["missed"] for day in tracked),
        },
    }


def _build_streak_data(tasks: list[dict]) -> dict:
    streaks = [int(task.get("streak", 0)) for task in tasks]
    longest = max(streaks) if streaks else 0
    daily = _daily_tasks(tasks)
    daily_streaks = [int(task.get("streak", 0)) for task in daily]
    return {
        "currentStreak": max(daily_streaks) if daily_streaks else 0,
        "bestStreak": longest,
        "activeTasks": len([task for task in tasks if task.get("streak", 0) > 0]),
    }


def _build_discipline_score_data(tasks: list[dict]) -> dict:
    total = len(tasks)
    completed = sum(1 for task in tasks if task.get("completed"))
    best_streak = max((int(task.get("streak", 0)) for task in tasks), default=0)
    score = round((completed / total) * 100) if total else 0
    return {
        "completed": completed,
        "total": total,
        "bestStreak": best_streak,
        "score": score,
        "progress": score,
    }


def _sanitize_task(task: dict) -> dict:
    return {
        "id": task.get("id"),
        "label": task.get("label"),
        "period": task.get("period"),
        "category": task.get("category", "general"),
        "streak": int(task.get("streak", 0)),
        "completed": bool(task.get("completed")),
        "completionLog": task.get("completionLog") or {},
    }


def _build_tasks_data(tasks: list[dict]) -> dict:
    sanitized = [_sanitize_task(task) for task in tasks if task.get("period") == "daily"]
    return {"tasks": sanitized}


def _build_habits_data(tasks: list[dict]) -> dict:
    grouped: dict[str, list] = {
        "daily": [],
        "weekly": [],
        "monthly": [],
        "yearly": [],
    }
    for task in tasks:
        period = task.get("period", "daily")
        if period in grouped:
            grouped[period].append(_sanitize_task(task))
    return {"tasksByPeriod": grouped}


def _build_shared_data(tasks: list[dict], allowed: set[str]) -> dict:
    data: dict = {}
    if "calendar" in allowed:
        data["calendar"] = _build_calendar_data(tasks)
    if "streak" in allowed:
        data["streak"] = _build_streak_data(tasks)
    if "discipline_score" in allowed:
        data["discipline_score"] = _build_discipline_score_data(tasks)
    if "tasks" in allowed:
        data["tasks"] = _build_tasks_data(tasks)
    if "habits" in allowed:
        data["habits"] = _build_habits_data(tasks)
    if "analytics" in allowed:
        data["analytics"] = build_analytics(tasks)
    return data


class ShareService:
    def __init__(
        self,
        share_repository: ShareRepository,
        task_repository: TaskRepository,
        user_repository: UserRepository,
    ) -> None:
        self._shares = share_repository
        self._tasks = task_repository
        self._users = user_repository

    def list_shares(self, owner_id: str) -> list[dict]:
        return self._shares.list_by_owner(owner_id)

    def list_incoming_shares(self, viewer_id: str, viewer_email: str) -> list[dict]:
        self._shares.link_recipient_user(viewer_email, viewer_id)
        return self._shares.list_by_recipient(viewer_email)

    def create_share(self, owner_id: str, payload: ShareCreateRequest) -> dict:
        owner = self._users.find_by_id(owner_id)
        if not owner:
            raise AppError("User not found.", status_code=404, code="NOT_FOUND")

        recipient = payload.recipient_email.lower().strip()
        if recipient == owner.email.lower():
            raise AppError(
                "You cannot share progress with yourself.",
                status_code=400,
                code="VALIDATION_ERROR",
            )

        resources = self._normalize_resources(payload.resources)
        expires_at = None
        if payload.expires_in_days:
            expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)

        token = secrets.token_urlsafe(32)
        share = self._shares.create(
            owner_id,
            owner_name=owner.name,
            owner_email=owner.email,
            recipient_email=recipient,
            resources=resources,
            token_hash=_hash_token(token),
            expires_at=expires_at,
        )

        return {
            "share": share,
            "shareToken": token,
            "sharePath": f"/shared/{token}",
        }

    def revoke_share(self, owner_id: str, share_id: str) -> bool:
        return self._shares.revoke(owner_id, share_id)

    def get_incoming_share(self, share_id: str, viewer_id: str, viewer_email: str) -> dict:
        share_doc = self._resolve_recipient_share(share_id, viewer_id, viewer_email)
        return {
            "id": str(share_doc["_id"]),
            "ownerId": share_doc["owner_id"],
            "ownerName": share_doc.get("owner_name") or "Discipline OS user",
            "ownerEmail": share_doc.get("owner_email"),
            "recipientEmail": share_doc["recipient_email"],
            "resources": [
                {"name": r["name"], "permission": r.get("permission", "view")}
                for r in share_doc.get("resources", [])
            ],
            "status": share_doc.get("status", "active"),
            "expiresAt": share_doc["expires_at"].isoformat()
            if share_doc.get("expires_at")
            else None,
            "createdAt": share_doc["created_at"].isoformat(),
            "updatedAt": share_doc["updated_at"].isoformat(),
        }

    def get_incoming_share_data(
        self, share_id: str, viewer_id: str, viewer_email: str
    ) -> dict:
        share_doc = self._resolve_recipient_share(share_id, viewer_id, viewer_email)
        owner_name = share_doc.get("owner_name") or "Discipline OS user"
        tasks = self._tasks.list_by_user(share_doc["owner_id"])
        allowed = {resource["name"] for resource in share_doc.get("resources", [])}
        return {
            "shareId": str(share_doc["_id"]),
            "ownerName": owner_name,
            "ownerId": share_doc["owner_id"],
            "resources": sorted(allowed),
            "data": _build_shared_data(tasks, allowed),
        }

    def get_share_preview(self, token: str, viewer_email: str) -> dict:
        share_doc = self._resolve_share(token, viewer_email)
        return {
            "ownerName": share_doc.get("owner_name") or "Discipline OS user",
            "recipientEmail": share_doc["recipient_email"],
            "resources": [
                {"name": r["name"], "permission": r.get("permission", "view")}
                for r in share_doc.get("resources", [])
            ],
            "status": share_doc.get("status", "active"),
            "expiresAt": share_doc["expires_at"].isoformat()
            if share_doc.get("expires_at")
            else None,
        }

    def get_shared_data(self, token: str, viewer_email: str) -> dict:
        share_doc = self._resolve_share(token, viewer_email)
        owner_name = share_doc.get("owner_name") or "Discipline OS user"
        tasks = self._tasks.list_by_user(share_doc["owner_id"])
        allowed = {resource["name"] for resource in share_doc.get("resources", [])}
        return {
            "ownerName": owner_name,
            "resources": sorted(allowed),
            "data": _build_shared_data(tasks, allowed),
        }

    def _resolve_recipient_share(
        self, share_id: str, viewer_id: str, viewer_email: str
    ) -> dict:
        self._shares.link_recipient_user(viewer_email, viewer_id)
        share_doc = self._shares.find_for_recipient(share_id, viewer_email)
        if not share_doc:
            raise AppError("Share not found.", status_code=404, code="SHARE_NOT_FOUND")

        if share_doc.get("status") == "revoked":
            raise AppError("This share has been revoked.", status_code=403, code="SHARE_REVOKED")

        expires_at = share_doc.get("expires_at")
        if expires_at and ensure_utc(expires_at) < datetime.now(UTC):
            raise AppError("This share has expired.", status_code=403, code="SHARE_EXPIRED")

        return share_doc

    def _resolve_share(self, token: str, viewer_email: str) -> dict:
        if not token or len(token) < 16:
            raise AppError("Invalid share link.", status_code=404, code="SHARE_NOT_FOUND")

        share_doc = self._shares.find_by_token_hash(_hash_token(token))
        if not share_doc:
            decoded = unquote(token)
            if decoded != token:
                share_doc = self._shares.find_by_token_hash(_hash_token(decoded))
        if not share_doc:
            raise AppError("Share link not found.", status_code=404, code="SHARE_NOT_FOUND")

        if share_doc.get("status") == "revoked":
            raise AppError("This share link has been revoked.", status_code=403, code="SHARE_REVOKED")

        expires_at = share_doc.get("expires_at")
        if expires_at and ensure_utc(expires_at) < datetime.now(UTC):
            raise AppError("This share link has expired.", status_code=403, code="SHARE_EXPIRED")

        viewer = viewer_email.strip().lower()
        recipient = share_doc["recipient_email"].lower()
        if recipient != viewer:
            raise AppError(
                f"This link was shared with {recipient}. You're signed in as {viewer}. "
                "Check Friend Progress in the sidebar or sign in with the invited email.",
                status_code=403,
                code="SHARE_FORBIDDEN",
            )

        return share_doc

    @staticmethod
    def _normalize_resources(resources: list) -> list[dict]:
        seen: set[str] = set()
        normalized: list[dict] = []

        for resource in resources:
            name = resource.name.strip().lower()
            if name not in VALID_SHARE_RESOURCES:
                raise AppError(
                    f"Invalid resource: {name}.",
                    status_code=400,
                    code="VALIDATION_ERROR",
                )
            if name in seen:
                continue
            seen.add(name)
            permission = resource.permission or "view"
            if permission != "view":
                raise AppError(
                    "Only view permission is supported.",
                    status_code=400,
                    code="VALIDATION_ERROR",
                )
            normalized.append({"name": name, "permission": "view"})

        if not normalized:
            raise AppError(
                "Select at least one resource to share.",
                status_code=400,
                code="VALIDATION_ERROR",
            )

        return normalized
