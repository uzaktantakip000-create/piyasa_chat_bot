"""
Authentication routes.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from database import (
    get_db,
    authenticate_user,
    rotate_user_api_key,
    create_user_session,
    invalidate_session,
)
from schemas import LoginRequest, LoginResponse, RotateApiKeyRequest, UserInfoResponse
from backend.api.dependencies import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_MAX_AGE,
    SESSION_TTL_HOURS,
    viewer_dependencies,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    User login with username/password and optional TOTP MFA.
    Returns API key and sets session cookie.
    """
    logger.info("Login attempt for username: %s (totp: %s)", payload.username, bool(payload.totp))
    user = authenticate_user(db, payload.username, payload.password, payload.totp)
    if not user:
        logger.warning("Login failed for username: %s", payload.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials or MFA code")

    api_key = rotate_user_api_key(db, user)
    logger.info("User %s performed login and API key rotation", user.username)

    session_token, session = create_user_session(
        db,
        user,
        ttl_hours=SESSION_TTL_HOURS,
        user_agent=request.headers.get("user-agent"),
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
        path=SESSION_COOKIE_PATH,
    )
    response.headers["X-Session-Expires"] = session.expires_at.replace(microsecond=0).isoformat() + "Z"

    return LoginResponse(api_key=api_key, role=user.role, session_expires_at=session.expires_at)


@router.post("/rotate-api-key", response_model=LoginResponse)
def rotate_api_key(payload: RotateApiKeyRequest, db: Session = Depends(get_db)):
    """
    Manually rotate user API key.
    Requires username, password, and optional TOTP MFA.
    """
    user = authenticate_user(db, payload.username, payload.password, payload.totp)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials or MFA code")

    api_key = rotate_user_api_key(db, user)
    logger.info("User %s manually rotated API key", user.username)

    return LoginResponse(api_key=api_key, role=user.role)


@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    """
    Logout user by invalidating session and clearing session cookie.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        invalidate_session(db, token)

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        samesite=SESSION_COOKIE_SAMESITE,
    )

    return {"ok": True}


@router.get("/me", response_model=UserInfoResponse, dependencies=viewer_dependencies)
def me(request: Request):
    """
    Get current authenticated user information.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing user context")

    return UserInfoResponse(
        username=user.username,
        role=user.role,
        api_key_last_rotated=user.api_key_last_rotated,
    )
