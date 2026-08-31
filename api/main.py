"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routers import chat, configuration, dashboard, nodes, projects, quizzes, resources, roadmaps, reviews
from learning_ext.application import (
    ApplicationError,
    NodeNotFoundError,
    ProjectNotFoundError,
)
from learning_ext.observability import current_request_id, reset_request_id, set_request_id

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from learning_ext.bootstrap import init_learning_ext
    from learning_ext.application import (
        resume_content_preparation_jobs,
        shutdown_content_preparation_jobs,
    )
    from ktem.db.engine import engine
    from sqlmodel import Session

    init_learning_ext()
    with Session(engine) as session:
        resumed = resume_content_preparation_jobs(session)
    if resumed:
        import logging

        logging.getLogger("learning_ext.jobs").warning(
            "应用启动恢复了 %s 个内容准备作业", resumed
        )
    try:
        yield
    finally:
        shutdown_content_preparation_jobs()


def _frontend_out_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "frontend" / "out"


def create_app(frontend_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Learn Everything API", version="v1", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("x-request-id", "").strip() or uuid4().hex
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            logger.info(
                "HTTP 请求完成 request_id=%s method=%s path=%s status=%s",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
            )
            return response
        except Exception:
            logger.exception(
                "HTTP 请求异常 request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise
        finally:
            reset_request_id(token)

    @app.exception_handler(ProjectNotFoundError)
    @app.exception_handler(NodeNotFoundError)
    async def not_found_error(_request: Request, exc: ApplicationError):
        response = JSONResponse(status_code=404, content={"detail": str(exc)})
        response.headers["x-request-id"] = current_request_id()
        return response

    @app.exception_handler(ApplicationError)
    @app.exception_handler(ValueError)
    async def bad_request_error(_request: Request, exc: Exception):
        response = JSONResponse(status_code=400, content={"detail": str(exc)})
        response.headers["x-request-id"] = current_request_id()
        return response

    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(nodes.router, prefix="/api/v1")
    app.include_router(roadmaps.router, prefix="/api/v1")
    app.include_router(reviews.router, prefix="/api/v1")
    app.include_router(quizzes.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(resources.router, prefix="/api/v1")
    app.include_router(configuration.router, prefix="/api/v1")
    resolved_frontend_dir = frontend_dir if frontend_dir is not None else _frontend_out_dir()
    if os.environ.get("LEARNING_DEV_MODE") != "1" and resolved_frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=resolved_frontend_dir, html=True), name="frontend")
    return app


app = create_app()
