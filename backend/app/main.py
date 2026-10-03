from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, guides, sources, study
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.db.session import get_engine


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="HighSchoolNotes API", version="0.1.0", openapi_url="/api/v1/openapi.json")
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With", "Last-Event-ID"],
    )
    for router in (auth.router, sources.router, guides.router, study.router):
        app.include_router(router, prefix="/api/v1")

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        with get_engine().connect() as conn:
            conn.execute(text("select 1"))
        return {"ok": True}

    return app


app = create_app()
