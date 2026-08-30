from pydantic import BaseModel, ConfigDict, Field


class TaskCompletionEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    completed_at: str | None = Field(default=None, alias="completedAt")
    duration_minutes: int | None = Field(default=None, alias="durationMinutes")
    note: str | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str = Field(alias="userId")
    label: str
    description: str | None = None
    period: str
    completed: bool
    streak: int
    category: str = "general"
    priority: str | None = "medium"
    preferred_time: str | None = Field(default=None, alias="preferredTime")
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes")
    created_at: str = Field(alias="createdAt")
    completion_log: dict[str, TaskCompletionEntry] | None = Field(
        default=None, alias="completionLog"
    )


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str = Field(min_length=1, max_length=200)
    period: str = "daily"
    category: str = "general"
    description: str | None = Field(default=None, max_length=1000)
    priority: str | None = "medium"
    preferred_time: str | None = Field(default=None, alias="preferredTime")
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes", ge=0)


class TaskUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str | None = Field(default=None, min_length=1, max_length=200)
    period: str | None = None
    category: str | None = None
    description: str | None = Field(default=None, max_length=1000)
    priority: str | None = None
    preferred_time: str | None = Field(default=None, alias="preferredTime")
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes", ge=0)


class RecordCompletionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str = "done"
    date: str | None = None


class DashboardStats(BaseModel):
    completed: int
    total: int
    best_streak: int = Field(alias="bestStreak")
    score: int
    progress: int


class TasksByPeriod(BaseModel):
    daily: list[TaskResponse]
    weekly: list[TaskResponse]
    monthly: list[TaskResponse]
    yearly: list[TaskResponse]


class DashboardDataResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tasks: list[TaskResponse]
    tasks_by_period: TasksByPeriod = Field(alias="tasksByPeriod")
    stats: DashboardStats
    weekly_activity: list[int] = Field(alias="weeklyActivity")
    routines: list = Field(default_factory=list)
