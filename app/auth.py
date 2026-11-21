from fastapi import APIRouter, HTTPException, Response, status
from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.models import User
from app.schemas import AccessToken, Login, Register, UserRead
from app.security import (
    CurrentUser,
    dummy_password_hash,
    issue_access_token,
    password_hasher,
    unauthorized,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email already registered"}},
)
def register(payload: Register, db: DbSession) -> UserRead:
    user = User(
        email=payload.email,
        password_hash=password_hasher.hash(payload.password.get_secret_value()),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if isinstance(exc.orig, UniqueViolation) and exc.orig.diag.constraint_name == "uq_users_email":
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
        raise
    return UserRead.model_validate(user)


@router.post("/login", responses={401: {"description": "Invalid email or password"}})
def login(payload: Login, db: DbSession, response: Response) -> AccessToken:
    user = db.scalar(select(User).where(User.email == payload.email))
    stored_hash = user.password_hash if user is not None else dummy_password_hash
    verified = password_hasher.verify(payload.password.get_secret_value(), stored_hash)
    if user is None or not verified:
        raise unauthorized("Invalid email or password")

    response.headers["Cache-Control"] = "no-store"
    return issue_access_token(user)


@router.get("/me", responses={401: {"description": "Invalid or missing bearer token"}})
def read_profile(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
