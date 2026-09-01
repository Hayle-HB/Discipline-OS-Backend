from pydantic import BaseModel, ConfigDict, Field


class ShareCommentCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    body: str = Field(min_length=1, max_length=2000)
    parent_id: str | None = Field(default=None, alias="parentId")


class ShareCommentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    thread_key: str = Field(alias="threadKey")
    author_id: str = Field(alias="authorId")
    author_name: str = Field(alias="authorName")
    body: str
    parent_id: str | None = Field(default=None, alias="parentId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
