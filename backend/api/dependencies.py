"""
API dependencies - authentication and common utilities.
"""
import os
from typing import Optional
from http.cookies import SimpleCookie

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, get_user_by_api_key, get_user_by_session_token


# Session cookie configuration
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "piyasa.session")
SESSION_TTL_HOURS = int(os.getenv("DASHBOARD_SESSION_TTL_HOURS", "12"))
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
SESSION_COOKIE_PATH = os.getenv("SESSION_COOKIE_PATH", "/")
SESSION_MAX_AGE = SESSION_TTL_HOURS * 3600


class AuthenticatedUser(BaseModel):
    username: str
    role: str


_ROLE_PRIORITY = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


def _role_allows(user_role: str, required_role: str) -> bool:
    """Check if user role has sufficient permissions."""
    user_score = _ROLE_PRIORITY.get(user_role, 0)
    required_score = _ROLE_PRIORITY.get(required_role, 0)
    return user_score >= required_score


def _parse_session_cookie(raw_cookie: Optional[str]) -> Optional[str]:
    """Parse session cookie from raw cookie string."""
    if not raw_cookie:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(raw_cookie)
    except Exception:
        return None
    morsel = cookie.get(SESSION_COOKIE_NAME)
    if not morsel:
        return None
    return morsel.value


def require_role(required_role: str = "viewer"):
    """Dependency factory for role-based access control."""
    async def dependency(
        request: Request,
        x_api_key: str = Header(None, alias="X-API-Key"),
        db: Session = Depends(get_db),
    ) -> AuthenticatedUser:
        # Allow CORS preflight
        if request.method == "OPTIONS":
            viewer = AuthenticatedUser(username="cors", role="viewer")
            request.state.user = viewer
            return viewer

        # Try session cookie first
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if session_token:
            session_user = get_user_by_session_token(db, session_token)
            if session_user:
                if not _role_allows(session_user.role, required_role):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
                request.state.user = session_user
                return AuthenticatedUser(username=session_user.username, role=session_user.role)

        # Try environment API key (legacy)
        expected = os.getenv("API_KEY")
        if expected and x_api_key == expected:
            env_user = AuthenticatedUser(username="env-admin", role="admin")
            request.state.user = env_user
            return env_user

        # Try user API key
        user = get_user_by_api_key(db, x_api_key or "")
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
        if not _role_allows(user.role, required_role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        request.state.user = user
        return AuthenticatedUser(username=user.username, role=user.role)

    return dependency


# Pre-defined dependencies for common roles
viewer_dependencies = [Depends(require_role("viewer"))]
operator_dependencies = [Depends(require_role("operator"))]
admin_dependencies = [Depends(require_role("admin"))]
