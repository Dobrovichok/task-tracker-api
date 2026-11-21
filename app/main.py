from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import auth, tasks
from app.config import get_auth_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_auth_settings()
    yield


app = FastAPI(title="Task Tracker API", version="1.0.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(tasks.router)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Validation errors can include the original request data, including passwords.
    details = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": details})
