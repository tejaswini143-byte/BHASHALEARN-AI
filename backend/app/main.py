"""FastAPI entry point for the BHASHALEARN backend."""
from fastapi import FastAPI

from .api.auth import router as auth_router
from .api.courses import router as courses_router
from .api.students import router as students_router
from .api.sessions import router as sessions_router
from .api.tutor import router as tutor_router
from .api.memories import router as memories_router
from .api.progress import router as progress_router
from .api.voice import router as voice_router
from .api.session_context import router as session_context_router
from .config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else get_settings()
    app = FastAPI(
        title=config.app_name,
        debug=config.debug,
        version="0.1.0",
        description="Backend API for BHASHALEARN AI.",
    )
    app.include_router(auth_router, prefix=config.api_prefix)
    app.include_router(students_router, prefix=config.api_prefix)
    app.include_router(courses_router, prefix=config.api_prefix)
    app.include_router(sessions_router, prefix=config.api_prefix)
    app.include_router(tutor_router, prefix=config.api_prefix)
    app.include_router(memories_router, prefix=config.api_prefix)
    app.include_router(progress_router, prefix=config.api_prefix)
    app.include_router(voice_router, prefix=config.api_prefix)
    app.include_router(session_context_router, prefix=config.api_prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "bhashalearn-api"}

    @app.get(f"{config.api_prefix}/health", tags=["health"])
    def api_health() -> dict[str, str]:
        return {"status": "ok", "service": "bhashalearn-api"}

    return app


app = create_app()
