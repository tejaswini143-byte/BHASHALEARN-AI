"""FastAPI entry point for the BHASHALEARN backend."""
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from .api.auth import router as auth_router
from .api.courses import router as courses_router
from .api.students import router as students_router
from .api.sessions import router as sessions_router
from .api.tutor import router as tutor_router
from .api.memories import router as memories_router
from .api.progress import router as progress_router
from .api.assessments import router as assessments_router
from .api.quizzes import router as quizzes_router
from .api.voice import router as voice_router
from .api.session_context import router as session_context_router
from .api.documents import router as documents_router
from .api.missions import router as missions_router
from .api.assistant import router as assistant_router
from .api.analytics import router as analytics_router
from .api.knowledge import router as knowledge_router
from .api.research import router as research_router
from .api.career import router as career_router
from .config import Settings, get_settings
from .db.session import get_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else get_settings()
    app = FastAPI(
        title=config.app_name,
        debug=config.debug,
        version="0.1.0",
        description="Backend API for BHASHALEARN AI. Explicit document indexing and semantic search send extracted text and queries to the configured Gemini embedding provider.",
    )
    app.include_router(auth_router, prefix=config.api_prefix)
    app.include_router(students_router, prefix=config.api_prefix)
    app.include_router(courses_router, prefix=config.api_prefix)
    app.include_router(sessions_router, prefix=config.api_prefix)
    app.include_router(tutor_router, prefix=config.api_prefix)
    app.include_router(memories_router, prefix=config.api_prefix)
    app.include_router(progress_router, prefix=config.api_prefix)
    app.include_router(assessments_router, prefix=config.api_prefix)
    app.include_router(quizzes_router, prefix=config.api_prefix)
    app.include_router(voice_router, prefix=config.api_prefix)
    app.include_router(session_context_router, prefix=config.api_prefix)
    app.include_router(documents_router, prefix=config.api_prefix)
    app.include_router(missions_router, prefix=config.api_prefix)
    app.include_router(assistant_router, prefix=config.api_prefix)
    app.include_router(analytics_router, prefix=config.api_prefix)
    app.include_router(knowledge_router, prefix=config.api_prefix)
    app.include_router(research_router, prefix=config.api_prefix)
    app.include_router(career_router, prefix=config.api_prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "bhashalearn-api"}

    @app.get(f"{config.api_prefix}/health", tags=["health"])
    def api_health() -> dict[str, str]:
        return {"status": "ok", "service": "bhashalearn-api"}

    def database_readiness() -> dict[str, str]:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            # Keep connection strings, driver errors, and credentials out of the response.
            raise HTTPException(status_code=503, detail="Database is unavailable") from exc
        return {"status": "ready", "database": "ok"}

    app.add_api_route("/ready", database_readiness, methods=["GET"], tags=["health"])
    app.add_api_route(f"{config.api_prefix}/ready", database_readiness, methods=["GET"], tags=["health"])

    return app


app = create_app()
