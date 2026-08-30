from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import close_client
from app.core.exceptions import AppError
from app.repositories.routine_repository import RoutineRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import error_response


@asynccontextmanager
async def lifespan(_: FastAPI):
    users = UserRepository()
    users.ensure_indexes()
    users.seed_demo_user()
    tasks = TaskRepository()
    tasks.ensure_indexes()
    routines = RoutineRepository()
    routines.ensure_indexes()
    yield
    close_client()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_, exc: AppError):
        return error_response(exc.error, status_code=exc.status_code, code=exc.code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_, exc: RequestValidationError):
        message = "Invalid request body."
        for err in exc.errors():
            if err.get("type") == "value_error":
                message = str(err.get("msg", message))
                break
        return error_response(message, status_code=400, code="VALIDATION_ERROR")

    @app.get("/")
    def root():
        return {
            "message": "Discipline OS API",
            "version": settings.app_version,
            "docs": "/docs",
        }

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
