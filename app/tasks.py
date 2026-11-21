from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import AfterValidator
from sqlalchemy import ColumnElement, delete, func, or_, select, update

from app.database import DbSession
from app.models import Role, Task, User
from app.schemas import TaskCreate, TaskFilters, TaskPage, TaskPatch, TaskRead, nonempty_patch
from app.security import CurrentUser


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    responses={401: {"description": "Invalid or missing bearer token"}},
)
not_found = {404: {"description": "Task not found"}}


def visible_tasks(user: User) -> tuple[ColumnElement[bool], ...]:
    if user.role is Role.ADMIN:
        return ()
    return (Task.owner_id == user.id,)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, user: CurrentUser, db: DbSession) -> TaskRead:
    task = Task(owner_id=user.id, **payload.model_dump())
    db.add(task)
    db.commit()
    return TaskRead.model_validate(task)


@router.get("")
def list_tasks(filters: Annotated[TaskFilters, Query()], user: CurrentUser, db: DbSession) -> TaskPage:
    conditions = list(visible_tasks(user))
    if filters.status is not None:
        conditions.append(Task.status == filters.status)
    if filters.priority is not None:
        conditions.append(Task.priority == filters.priority)
    if filters.owner_id is not None:
        conditions.append(Task.owner_id == filters.owner_id)
    if filters.due_to is not None:
        conditions.append(Task.due_date <= filters.due_to)
    if filters.q is not None:
        conditions.append(
            or_(
                Task.title.icontains(filters.q, autoescape=True),
                Task.description.icontains(filters.q, autoescape=True),
            )
        )

    total = db.execute(select(func.count()).select_from(Task).where(*conditions)).scalar_one()
    tasks = db.scalars(
        select(Task)
        .where(*conditions)
        .order_by(Task.created_at.desc(), Task.id.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )
    return TaskPage(
        items=[TaskRead.model_validate(task) for task in tasks],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
    )


@router.get("/{task_id}", responses=not_found)
def read_task(task_id: UUID, user: CurrentUser, db: DbSession) -> TaskRead:
    task = db.scalar(select(Task).where(Task.id == task_id, *visible_tasks(user)))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return TaskRead.model_validate(task)


@router.patch("/{task_id}", responses=not_found)
def update_task(
    task_id: UUID,
    payload: Annotated[TaskPatch, AfterValidator(nonempty_patch)],
    user: CurrentUser,
    db: DbSession,
) -> TaskRead:
    task = db.scalar(
        update(Task)
        .where(Task.id == task_id, *visible_tasks(user))
        .values(**payload, updated_at=func.clock_timestamp())
        .returning(Task)
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    db.commit()
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, responses=not_found)
def delete_task(task_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    deleted_id = db.scalar(
        delete(Task).where(Task.id == task_id, *visible_tasks(user)).returning(Task.id)
    )
    if deleted_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
