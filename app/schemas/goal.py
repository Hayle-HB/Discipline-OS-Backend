from pydantic import BaseModel, ConfigDict, Field


VALID_GOAL_CATEGORIES = frozenset(
    {"career", "health", "finance", "education", "personal", "other"}
)
VALID_GOAL_PRIORITIES = frozenset({"low", "medium", "high"})


class GoalTaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    goal_id: str = Field(alias="goalId")
    title: str
    description: str | None = None
    completed: bool = False
    sort_order: int = Field(default=0, alias="sortOrder")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class GoalSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    description: str | None = None
    why: str | None = None
    deadline: str | None = None
    category: str = "personal"
    priority: str = "medium"
    status: str = "active"
    progress_percent: int = Field(default=0, alias="progressPercent")
    tasks_total: int = Field(default=0, alias="tasksTotal")
    tasks_completed: int = Field(default=0, alias="tasksCompleted")
    days_remaining: int | None = Field(default=None, alias="daysRemaining")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class GoalDetailResponse(GoalSummaryResponse):
    tasks: list[GoalTaskResponse] = Field(default_factory=list)


class GoalCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    why: str | None = Field(default=None, max_length=2000)
    deadline: str | None = Field(default=None, max_length=32)
    category: str = "personal"
    priority: str = "medium"


class GoalUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    why: str | None = Field(default=None, max_length=2000)
    deadline: str | None = Field(default=None, max_length=32)
    category: str | None = None
    priority: str | None = None


class GoalTaskCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class GoalTaskUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    completed: bool | None = None
