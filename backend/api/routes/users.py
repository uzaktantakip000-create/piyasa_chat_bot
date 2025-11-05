"""
User Management routes - CRUD operations for API users (admin only).
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db, ApiUser, create_user, update_user, delete_user, reset_user_mfa
from schemas import UserCreateRequest, UserUpdateRequest, UserListResponse
from backend.api.dependencies import admin_dependencies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])


def _user_to_response(user: ApiUser) -> UserListResponse:
    """Convert ApiUser model to UserListResponse schema."""
    return UserListResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        mfa_enabled=bool(user.mfa_secret),
        created_at=user.created_at,
        api_key_last_rotated=user.api_key_last_rotated,
    )


@router.get("/", response_model=List[UserListResponse], dependencies=admin_dependencies)
def list_users(db: Session = Depends(get_db)):
    """List all API users (admin only)."""
    users = db.query(ApiUser).order_by(ApiUser.created_at.desc()).all()
    return [_user_to_response(user) for user in users]


@router.post("/", response_model=UserListResponse, status_code=status.HTTP_201_CREATED, dependencies=admin_dependencies)
def create_new_user(request: UserCreateRequest, db: Session = Depends(get_db)):
    """Create a new API user (admin only)."""
    try:
        user = create_user(
            db=db,
            username=request.username,
            password=request.password,
            role=request.role,
            mfa_enabled=request.mfa_enabled,
        )
        logger.info(f"Admin created user '{request.username}' with role '{request.role}'")
        return _user_to_response(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to create user '{request.username}'")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")


@router.get("/{user_id}", response_model=UserListResponse, dependencies=admin_dependencies)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user details by ID (admin only)."""
    user = db.query(ApiUser).filter(ApiUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_response(user)


@router.patch("/{user_id}", response_model=UserListResponse, dependencies=admin_dependencies)
def update_existing_user(user_id: int, request: UserUpdateRequest, db: Session = Depends(get_db)):
    """Update user attributes (admin only)."""
    user = db.query(ApiUser).filter(ApiUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        updated_user = update_user(
            db=db,
            user=user,
            role=request.role,
            is_active=request.is_active,
            reset_password=request.reset_password,
        )
        logger.info(f"Admin updated user '{user.username}' (ID: {user_id})")
        return _user_to_response(updated_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to update user ID {user_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=admin_dependencies)
def delete_existing_user(user_id: int, db: Session = Depends(get_db)):
    """Delete (deactivate) user (admin only)."""
    user = db.query(ApiUser).filter(ApiUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deleting the last admin
    if user.role == "admin":
        admin_count = db.query(ApiUser).filter(
            ApiUser.role == "admin",
            ApiUser.is_active == True
        ).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin user"
            )

    try:
        delete_user(db=db, user=user)
        logger.info(f"Admin deleted user '{user.username}' (ID: {user_id})")
        return None
    except Exception as e:
        logger.exception(f"Failed to delete user ID {user_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete user")


@router.post("/{user_id}/reset-mfa", response_model=dict, dependencies=admin_dependencies)
def reset_mfa_secret(user_id: int, db: Session = Depends(get_db)):
    """Reset user's MFA secret (admin only)."""
    user = db.query(ApiUser).filter(ApiUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        new_secret = reset_user_mfa(db=db, user=user)
        logger.info(f"Admin reset MFA for user '{user.username}' (ID: {user_id})")
        return {
            "message": "MFA secret reset successfully",
            "mfa_secret": new_secret,
            "username": user.username
        }
    except Exception as e:
        logger.exception(f"Failed to reset MFA for user ID {user_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset MFA")
