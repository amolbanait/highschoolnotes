import uuid
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.core.security import hash_token
from app.db.models import Source, StudyGuide, User, UserSession
from app.db.session import get_db

SESSION_COOKIE = "hsn_session"
CSRF_HEADER = "X-Requested-With"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def csrf_guard(request: Request) -> None:
    """Cookie-authenticated writes must carry a custom header, which a cross-site form cannot send."""
    if request.method in UNSAFE_METHODS and not request.headers.get(CSRF_HEADER):
        raise AppError(
            403, "csrf_header_missing", f"Requests that change data must send the {CSRF_HEADER} header."
        )


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    hsn_session: str | None = Cookie(default=None),
) -> User:
    csrf_guard(request)
    if not hsn_session:
        raise AppError(401, "unauthorized", "Please sign in.")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(hsn_session)))
    if session is None or session.expires_at < datetime.now(UTC):
        raise AppError(401, "unauthorized", "Your session has ended. Please sign in again.")
    user = db.get(User, session.user_id)
    if user is None:
        raise AppError(401, "unauthorized", "Please sign in.")
    return user


def own_source(db: Session, user: User, source_id: uuid.UUID) -> Source:
    source = db.get(Source, source_id)
    if source is None or source.user_id != user.id:
        raise not_found("source")
    return source


def own_guide(db: Session, user: User, guide_id: uuid.UUID) -> StudyGuide:
    guide = db.get(StudyGuide, guide_id)
    if guide is None or guide.user_id != user.id:
        raise not_found("guide")
    return guide
