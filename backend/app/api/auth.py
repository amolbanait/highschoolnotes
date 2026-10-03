from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, csrf_guard, current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.db.models import Source, User, UserSession
from app.db.session import get_db
from app.schemas.api import LoginIn, SignupIn, UpdateMeIn, UserOut
from app.storage.files import get_storage

router = APIRouter(tags=["auth"])

# Verified against when the email is unknown, so response time does not reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


def _start_session(db: Session, response: Response, user: User) -> None:
    settings = get_settings()
    token = new_session_token()
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    db.add(UserSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/auth/signup", status_code=201, response_model=UserOut)
def signup(body: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    csrf_guard(request)
    if not body.confirms_age_13_plus:
        raise AppError(400, "age_requirement", "You must be 13 or older to create an account.")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip(),
        birth_year_confirmed_13plus=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists.") from exc
    _start_session(db, response, user)
    return user


@router.post("/auth/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    csrf_guard(request)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if user is None or not ok:
        raise AppError(401, "invalid_credentials", "That email and password do not match.")
    _start_session(db, response, user)
    return user


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    hsn_session: str | None = Cookie(default=None),
) -> Response:
    csrf_guard(request)
    if hsn_session:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(hsn_session)))
        db.commit()
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UpdateMeIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
    user = db.merge(user)
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if body.default_level is not None:
        user.default_level = body.default_level
    db.commit()
    return user


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    """Full delete: the account, every source file, segment, guide and study history."""
    storage = get_storage()
    for key in db.scalars(select(Source.storage_key).where(Source.user_id == user.id)):
        if key:
            storage.delete(key)
    db.delete(db.merge(user))  # cascades in the database
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
