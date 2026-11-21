from datetime import date, datetime
from typing import Annotated, Literal, TypedDict
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    with_config,
)

from app.models import Priority, Role, TaskStatus


EmailAddress = Annotated[EmailStr, AfterValidator(str.lower)]
NO_NULL_BYTE = r"^[^\x00]*$"
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160, pattern=NO_NULL_BYTE)
]
Description = Annotated[str, StringConstraints(max_length=5000, pattern=NO_NULL_BYTE)]
SearchText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100, pattern=NO_NULL_BYTE)
]


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Register(RequestBody):
    email: EmailAddress
    password: SecretStr = Field(min_length=12, max_length=128)


class Login(RequestBody):
    email: EmailAddress
    password: SecretStr = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: Role


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class TaskCreate(RequestBody):
    title: Title
    description: Description | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None


@with_config(ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1}))
class TaskPatch(TypedDict, total=False):
    title: Title
    description: Description | None
    status: TaskStatus
    priority: Priority
    due_date: date | None


def nonempty_patch(values: TaskPatch) -> TaskPatch:
    if not values:
        raise ValueError("Provide at least one field to update")
    return values


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: Priority
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class TaskFilters(RequestBody):
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int = Field(default=20, ge=1, le=100)
    status: TaskStatus | None = None
    priority: Priority | None = None
    owner_id: UUID | None = None
    q: SearchText | None = None
    due_to: date | None = None


class TaskPage(BaseModel):
    items: list[TaskRead]
    page: int
    page_size: int
    total: int
