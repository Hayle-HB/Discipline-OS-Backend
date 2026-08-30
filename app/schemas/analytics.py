from pydantic import BaseModel, ConfigDict, Field


class AnalyticsSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_commitments_completed: int = Field(alias="totalCommitmentsCompleted")
    current_streak: int = Field(alias="currentStreak")
    longest_streak: int = Field(alias="longestStreak")
    average_score: int = Field(alias="averageScore")
    days_tracked: int = Field(alias="daysTracked")


class MonthlyScore(BaseModel):
    month: str
    score: int


class StreakHistoryEntry(BaseModel):
    date: str
    score: int


class CategoryBreakdown(BaseModel):
    category: str
    completed: int
    total: int
    color: str


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    weekly_activity: list[int] = Field(alias="weeklyActivity")
    monthly_scores: list[MonthlyScore] = Field(alias="monthlyScores")
    streak_history: list[StreakHistoryEntry] = Field(alias="streakHistory")
    category_breakdown: list[CategoryBreakdown] = Field(alias="categoryBreakdown")
    insights: list[str]
    summary: AnalyticsSummary
