"""Compute analytics from task documents (camelCase API shape)."""

from __future__ import annotations

from calendar import month_abbr
from collections import defaultdict
from datetime import date, timedelta

from app.repositories.task_repository import TaskRepository
from app.utils.periods import normalize_completion_log, to_date_key

CATEGORY_COLORS = {
    "health": "#38bdf8",
    "focus": "#fbbf24",
    "growth": "#34d399",
    "mindfulness": "#a78bfa",
    "finance": "#f472b6",
    "general": "#94a3b8",
}


def _daily_tasks(tasks: list[dict]) -> list[dict]:
    return [t for t in tasks if t.get("period") == "daily"]


def _day_score(daily_tasks: list[dict], day: date) -> int:
    if not daily_tasks:
        return 0
    key = to_date_key(day)
    done = 0
    for task in daily_tasks:
        log = task.get("completionLog") or {}
        entry = log.get(key)
        if entry and entry.get("status") == "done":
            done += 1
    return round((done / len(daily_tasks)) * 100)


def _count_done_entries(tasks: list[dict]) -> int:
    total = 0
    for task in tasks:
        log = normalize_completion_log(task.get("completionLog"))
        for entry in log.values():
            if entry.get("status") == "done":
                total += 1
    return total


def _distinct_tracked_days(tasks: list[dict]) -> int:
    days: set[str] = set()
    for task in tasks:
        log = normalize_completion_log(task.get("completionLog"))
        days.update(log.keys())
    return len(days)


def _build_insights(
    tasks: list[dict],
    daily: list[dict],
    weekly_activity: list[int],
    current_streak: int,
    category_breakdown: list[dict],
) -> list[str]:
    insights: list[str] = []

    if not tasks:
        return ["Start tracking tasks to unlock personalized insights."]

    if current_streak >= 3:
        insights.append(f"Your best active streak is {current_streak} days — keep showing up.")

    if len(weekly_activity) >= 2:
        recent = weekly_activity[-1]
        prior = weekly_activity[-2]
        if recent > prior:
            insights.append(f"Today's completion rate ({recent}%) is up from yesterday ({prior}%).")
        elif recent < prior:
            insights.append(f"Completion dipped to {recent}% today. A small win still counts.")

    if category_breakdown:
        best = max(category_breakdown, key=lambda c: (c["completed"] / c["total"]) if c["total"] else 0)
        if best["total"] > 0:
            rate = round((best["completed"] / best["total"]) * 100)
            insights.append(f"{best['category']} is your strongest area today at {rate}% complete.")

    if len(daily) >= 5:
        insights.append("You have a solid daily lineup — focus on consistency over perfection.")

    return insights[:4]


def build_analytics(tasks: list[dict]) -> dict:
    daily = _daily_tasks(tasks)

    weekly_activity = [_day_score(daily, date.today() - timedelta(days=i)) for i in range(6, -1, -1)]

    streak_history = [
        {
            "date": to_date_key(date.today() - timedelta(days=i)),
            "score": _day_score(daily, date.today() - timedelta(days=i)),
        }
        for i in range(6, -1, -1)
    ]

    monthly_scores: list[dict] = []
    today = date.today()
    for offset in range(3, -1, -1):
        month = today.month - offset
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        first = date(year, month, 1)
        if month == 12:
            last = date(year, 12, 31)
        else:
            last = date(year, month + 1, 1) - timedelta(days=1)

        scores: list[int] = []
        cursor = first
        while cursor <= last and cursor <= today:
            scores.append(_day_score(daily, cursor))
            cursor += timedelta(days=1)

        avg = round(sum(scores) / len(scores)) if scores else 0
        monthly_scores.append({"month": month_abbr[month], "score": avg})

    category_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"completed": 0, "total": 0})
    for task in daily:
        cat = (task.get("category") or "general").lower()
        category_stats[cat]["total"] += 1
        if task.get("completed"):
            category_stats[cat]["completed"] += 1

    category_breakdown = [
        {
            "category": cat.title(),
            "completed": stats["completed"],
            "total": stats["total"],
            "color": CATEGORY_COLORS.get(cat, CATEGORY_COLORS["general"]),
        }
        for cat, stats in sorted(category_stats.items())
    ]

    streaks = [int(t.get("streak", 0)) for t in tasks]
    longest = [int(t.get("streak", 0)) for t in tasks]
    current_streak = max(streaks) if streaks else 0
    longest_streak = max(longest) if longest else 0

    avg_score = round(sum(weekly_activity) / len(weekly_activity)) if weekly_activity else 0
    days_tracked = _distinct_tracked_days(tasks)

    insights = _build_insights(tasks, daily, weekly_activity, current_streak, category_breakdown)

    return {
        "weeklyActivity": weekly_activity,
        "monthlyScores": monthly_scores,
        "streakHistory": streak_history,
        "categoryBreakdown": category_breakdown,
        "insights": insights,
        "summary": {
            "totalCommitmentsCompleted": _count_done_entries(tasks),
            "currentStreak": current_streak,
            "longestStreak": longest_streak,
            "averageScore": avg_score,
            "daysTracked": days_tracked,
        },
    }


class AnalyticsService:
    def __init__(self, task_repository: TaskRepository) -> None:
        self._tasks = task_repository

    def get_analytics(self, user_id: str) -> dict:
        tasks = self._tasks.list_by_user(user_id)
        return build_analytics(tasks)
