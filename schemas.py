from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr, ConfigDict
from datetime import datetime
from typing import Literal

class UserRequest(BaseModel):
    email: EmailStr
    password: str =Field(min_length=8)

    @field_validator("password")
    @classmethod
    def no_blank(cls, password: str) -> str:
        if not password.strip():
            raise ValueError("Password can't be blank.")
        return password

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    email: str
    created_at: datetime

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default = None, max_length=200)
    priority: int = Field(ge = 1, le = 100)

    @field_validator("title")
    @classmethod
    def no_blank(cls, title: str) -> str:
        if not title.strip():
            raise ValueError("Title can't be blank.")
        return title

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    description: str | None
    completed: bool
    priority: int
    created_at: datetime
    user_id: int

class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
    offset: int
    limit: int

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=200)
    completed: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=100)

    @field_validator("title")
    @classmethod
    def no_blank(cls, title: str | None) -> str | None:
        if title is not None and not title.strip():
            raise ValueError("Title can't be blank.")
        return title

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")

        for field in ("title", "completed", "priority"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")

        return self

class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"]

class AIAnalyzeRequest(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural-language request describing how the user wants their tasks analyzed."
        )

class Recommendation(BaseModel):
    task_id: int
    reason: str = Field(max_length=300)

class AIResponse(BaseModel):
    summary: str = Field(max_length=500)
    recommendations: list[Recommendation] = Field(max_length=10, description="Recommendation.task_id is not repeatable.")

    @field_validator("recommendations")
    @classmethod
    def check_unique_ids(cls, v: list[Recommendation]) -> list[Recommendation]:
        ids = [recommendation.task_id for recommendation in v]
        
        if len(ids) != len(set(ids)):
            raise ValueError("Task_id is not repeatable.")
            
        return v
