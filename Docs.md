# Discipline OS — Task Data Model (Reference)

> **Reference only.** This document defines the recommended MongoDB schema and rules for tasks in the FastAPI backend. It aligns with the Discipline OS frontend (`discipline-os/lib/data/types.ts`) and extends it for production use.

---

## Design principles

1. **Source of truth for history** — completion records, not a cached `streak` field.
2. **Period-aware keys** — daily / weekly / monthly / yearly tasks use different log keys (same rules as the frontend).
3. **User isolation** — every task and completion is scoped by `user_id`.
4. **Denormalized read fields** — `completed` (today) and `streak` are computed on write and stored for fast dashboard loads.
5. **Separate completions collection** — avoids unbounded embedded arrays and keeps task documents small.

---

## Collections

| Collection           | Purpose                                      |
|----------------------|----------------------------------------------|
| `tasks`              | Task definition + denormalized summary       |
| `task_completions`   | One document per task × period key           |

---

## 1. Task document (`tasks`)

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "label": "Morning workout",
  "description": "45 min strength or cardio",
  "period": "daily",
  "category": "health",
  "priority": "high",
  "preferred_time": "06:30",
  "estimated_minutes": 45,
  "status": "active",
  "tags": ["fitness", "morning"],
  "sort_order": 0,
  "completed": false,
  "streak": 12,
  "longest_streak": 18,
  "created_at": "2026-01-20T06:00:00.000Z",
  "updated_at": "2026-08-30T19:00:00.000Z",
  "archived_at": null
}
```

### Field reference

| Field               | Type     | Required | Notes |
|---------------------|----------|----------|-------|
| `_id`               | ObjectId | yes      | MongoDB primary key; expose as string `id` in API |
| `user_id`           | ObjectId | yes      | Owner; indexed |
| `label`             | string   | yes      | 1–200 chars, trimmed |
| `description`       | string   | no       | Optional details for Manage view |
| `period`            | enum     | yes      | `daily` \| `weekly` \| `monthly` \| `yearly` |
| `category`          | string   | yes      | Default `"general"`; used in analytics breakdown |
| `priority`          | enum     | no       | `low` \| `medium` \| `high`; default `medium` |
| `preferred_time`    | string   | no       | 24h `"HH:mm"` for UI sorting |
| `estimated_minutes` | int      | no       | ≥ 0 |
| `status`            | enum     | yes      | `active` \| `archived` \| `paused` |
| `tags`              | string[] | no       | Optional filtering / future search |
| `sort_order`        | int      | no       | Per-user ordering within a period tab |
| `completed`         | bool     | yes      | **Denormalized:** done for *current* period (usually today) |
| `streak`            | int      | yes      | **Denormalized:** consecutive done periods ending at reference date |
| `longest_streak`    | int      | yes      | **Denormalized:** all-time best for this task |
| `created_at`        | datetime | yes      | UTC |
| `updated_at`        | datetime | yes      | UTC |
| `archived_at`       | datetime | no       | Set when `status === "archived"` |

### Indexes

```javascript
db.tasks.createIndex({ user_id: 1, status: 1, period: 1, sort_order: 1 })
db.tasks.createIndex({ user_id: 1, created_at: -1 })
```

---

## 2. Task completion document (`task_completions`)

One row per **task + period key** (not per calendar day for weekly/monthly/yearly tasks).

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "task_id": "ObjectId",
  "period": "daily",
  "period_key": "2026-08-30",
  "status": "done",
  "completed_at": "2026-08-30T10:32:00.000Z",
  "duration_minutes": 45,
  "note": "Felt strong today",
  "created_at": "2026-08-30T10:32:00.000Z",
  "updated_at": "2026-08-30T10:32:00.000Z"
}
```

### Period keys (must match frontend)

| Period   | Key format   | Example        |
|----------|--------------|----------------|
| daily    | `YYYY-MM-DD` | `2026-08-30`   |
| weekly   | `YYYY-Www`   | `2026-W35`     |
| monthly  | `YYYY-MM`    | `2026-08`      |
| yearly   | `YYYY`       | `2026`         |

Use ISO week (Mon-based), same as `getISOWeekKey()` in `discipline-os/lib/data/dates.ts`.

### Field reference

| Field              | Type     | Required | Notes |
|--------------------|----------|----------|-------|
| `user_id`          | ObjectId | yes      | Denormalized for user-scoped calendar queries |
| `task_id`          | ObjectId | yes      | Parent task |
| `period`           | enum     | yes      | Copied from task for filtering |
| `period_key`       | string   | yes      | Unique per task (see table above) |
| `status`           | enum     | yes      | `done` \| `missed` |
| `completed_at`     | datetime | no       | Set when `status === "done"` |
| `duration_minutes` | int      | no       | Optional time tracking |
| `note`             | string   | no       | Optional reflection |

### Indexes

```javascript
db.task_completions.createIndex(
  { task_id: 1, period_key: 1 },
  { unique: true }
)
db.task_completions.createIndex({ user_id: 1, period: 1, period_key: 1 })
db.task_completions.createIndex({ user_id: 1, period_key: 1, status: 1 })
```

---

## 3. Streak rules (reference)

Computed in the service layer after every completion write; stored on the task document.

| Current period state | Streak behavior |
|----------------------|-----------------|
| **done**             | Count consecutive `done` periods backward, including current |
| **pending** (no row) | Count from previous period backward (grace until logged) |
| **missed**           | Streak = `0` (chain broken) |

Update `longest_streak` when `streak > longest_streak`.

---

## 4. API shapes (aligned with frontend)

### Create task — `POST /api/tasks`

```json
{
  "label": "Read 30 minutes",
  "period": "daily",
  "category": "growth",
  "description": "Non-fiction or personal growth",
  "priority": "medium",
  "preferredTime": "21:00",
  "estimatedMinutes": 30
}
```

### Record completion — `PATCH /api/tasks/{id}`

```json
{
  "status": "done",
  "date": "2026-08-30"
}
```

- `date` optional; defaults to today (user timezone or UTC — pick one and document in config).
- Upserts `task_completions` for `(task_id, period_key)`.
- Recomputes `completed`, `streak`, `longest_streak` on the task.

### Task response (API → frontend)

Map MongoDB fields to camelCase for the Next.js client:

```json
{
  "id": "68b1a2...",
  "userId": "68b1a0...",
  "label": "Morning workout",
  "description": "45 min strength or cardio",
  "period": "daily",
  "completed": true,
  "streak": 12,
  "category": "health",
  "priority": "high",
  "preferredTime": "06:30",
  "estimatedMinutes": 45,
  "createdAt": "2026-01-20T06:00:00.000Z",
  "completionLog": {
    "2026-08-30": {
      "status": "done",
      "completedAt": "2026-08-30T10:32:00.000Z",
      "durationMinutes": 45
    }
  }
}
```

`completionLog` can be:

- **Embedded in list response** — last N keys (e.g. 30 days) for calendar UI, or
- **Loaded on demand** — `GET /api/tasks/{id}/completions?from=&to=` for history views.

For dashboard list, returning recent log entries (or building `completionLog` from `task_completions` query) keeps the frontend unchanged.

---

## 5. Pydantic models (backend reference)

```python
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field


class TaskPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class TaskDayStatus(StrEnum):
    DONE = "done"
    MISSED = "missed"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    PAUSED = "paused"


class TaskCompletionEntry(BaseModel):
    status: TaskDayStatus
    completed_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class TaskCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    period: TaskPeriod
    category: str = "general"
    description: str | None = Field(default=None, max_length=1000)
    priority: TaskPriority = TaskPriority.MEDIUM
    preferred_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    estimated_minutes: int | None = Field(default=None, ge=0)


class TaskUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    period: TaskPeriod | None = None
    category: str | None = None
    description: str | None = None
    priority: TaskPriority | None = None
    preferred_time: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)
    status: TaskStatus | None = None
    sort_order: int | None = None


class RecordCompletion(BaseModel):
    status: TaskDayStatus
    date: str | None = None  # YYYY-MM-DD; resolved to period_key server-side
```

---

## 6. Service flow (write path)

```
PATCH /api/tasks/{id}  { status, date }
        │
        ▼
  Resolve period_key from task.period + date
        │
        ▼
  Upsert task_completions (task_id + period_key)
        │
        ▼
  Load recent completions for task
        │
        ▼
  compute_streak(completions, period, reference_date)
        │
        ▼
  Update tasks: completed, streak, longest_streak, updated_at
        │
        ▼
  Return Task (with completionLog slice for frontend)
```

---

## 7. Optional extensions (future)

| Feature            | Approach |
|--------------------|----------|
| Reminders          | `reminder_time`, `reminder_enabled` on task |
| Subtasks           | `subtasks: [{ id, label, done }]` embedded (small lists only) |
| Soft delete        | `status: "archived"` + `archived_at` |
| Timezone           | Store `user_timezone` on user; resolve “today” in that zone |
| Analytics rollups  | Nightly job → `user_daily_stats` collection |

---

## 8. Migration from demo JSON

When seeding a new user from `demo.json`:

1. Insert `tasks` without `completionLog`.
2. Expand each demo completion into `task_completions` rows.
3. Recompute `streak` / `longest_streak` from completions (do not trust demo `streak` alone).

---

*Last updated: reference for Backend implementation — not enforced until tasks API is built.*
