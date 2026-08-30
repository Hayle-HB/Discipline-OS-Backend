"""Period keys and streak logic — mirrors discipline-os/lib/data/dates.ts + task-completions.ts"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal

TaskPeriod = Literal["daily", "weekly", "monthly", "yearly"]
TaskDayStatus = Literal["done", "missed"]


def to_date_key(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def today_key() -> str:
    return to_date_key(date.today())


def parse_date_key(key: str) -> date:
    year, month, day = (int(part) for part in key.split("-"))
    return date(year, month, day)


def add_days(value: date, days: int) -> date:
    return value + timedelta(days=days)


def get_iso_week_key(value: date) -> str:
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def get_month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def get_year_key(value: date) -> str:
    return str(value.year)


def get_period_log_key(value: date, period: TaskPeriod) -> str:
    if period == "daily":
        return to_date_key(value)
    if period == "weekly":
        return get_iso_week_key(value)
    if period == "monthly":
        return get_month_key(value)
    return get_year_key(value)


def step_period_back(value: date, period: TaskPeriod) -> date:
    if period == "weekly":
        return add_days(value, -7)
    if period == "monthly":
        year, month = value.year, value.month - 1
        if month == 0:
            month, year = 12, year - 1
        max_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(value.day, max_day))
    if period == "yearly":
        try:
            return date(value.year - 1, value.month, value.day)
        except ValueError:
            return date(value.year - 1, value.month, 28)
    return add_days(value, -1)


def normalize_completion_log(
    log: dict | None,
) -> dict[str, dict]:
    if not log:
        return {}
    out: dict[str, dict] = {}
    for key, entry in log.items():
        if isinstance(entry, str):
            out[key] = {"status": entry}
        else:
            out[key] = dict(entry)
    return out


def compute_task_streak(
    period: TaskPeriod,
    completion_log: dict | None,
    reference: date | None = None,
) -> int:
    log = normalize_completion_log(completion_log)
    ref = reference or date.today()
    today_period_key = get_period_log_key(date.today(), period)
    cursor = ref
    ref_key = get_period_log_key(cursor, period)
    ref_entry = log.get(ref_key)

    if ref_key == today_period_key:
        if ref_entry and ref_entry.get("status") == "missed":
            return 0
        if not ref_entry or ref_entry.get("status") != "done":
            cursor = step_period_back(cursor, period)
    elif ref_entry and ref_entry.get("status") == "missed":
        return 0
    elif not ref_entry or ref_entry.get("status") != "done":
        cursor = step_period_back(cursor, period)

    streak = 0
    for _ in range(366):
        key = get_period_log_key(cursor, period)
        entry = log.get(key)
        if entry and entry.get("status") == "done":
            streak += 1
            cursor = step_period_back(cursor, period)
        else:
            break
    return streak


def normalize_task_fields(
    period: TaskPeriod,
    completion_log: dict | None,
    reference: date | None = None,
) -> tuple[bool, int]:
    log = normalize_completion_log(completion_log)
    ref = reference or date.today()
    today_period_key = get_period_log_key(date.today(), period)
    completed = log.get(today_period_key, {}).get("status") == "done"
    streak = compute_task_streak(period, log, ref)
    return completed, streak
