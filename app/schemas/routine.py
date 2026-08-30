from pydantic import BaseModel, ConfigDict, Field


class RoutineStepResponse(BaseModel):
    id: str
    label: str
    completed: bool


class RoutineResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str = Field(alias="userId")
    name: str
    description: str
    steps: list[RoutineStepResponse]
    completed_today: bool = Field(alias="completedToday")


class ToggleRoutineStepRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    routine_id: str = Field(alias="routineId")
    step_id: str = Field(alias="stepId")
