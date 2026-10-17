"""FastAPI entry point: middleware, routers from app/api/ and the health check."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import auth, projects, team
from app.core.config import settings
from app.core.db import get_db

app = FastAPI(title="ReqGuard API", version="0.1.0")

# Allow the Next.js frontend to call the API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(team.router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Liveness check: the API is up and the database answers a simple query."""
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "ok",
        "db_engine": db.get_bind().dialect.name,
    }
