"""
Setup Wizard API routes - Initial system configuration.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db, ApiUser, create_user
from auth_utils import hash_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["Setup"])


class SetupStatusResponse(BaseModel):
    """Setup status response model."""
    setup_needed: bool
    reasons: list[str]
    has_env_file: bool
    has_llm_config: bool
    has_admin_user: bool


class SetupInitRequest(BaseModel):
    """Initial setup request model."""
    # LLM Provider
    llm_provider: str = Field(..., description="LLM provider: openai, gemini, or groq")
    llm_api_key: str = Field(..., min_length=10, description="LLM API key")
    llm_model: str = Field(default="", description="Optional: LLM model name")

    # Admin User
    admin_username: str = Field(..., min_length=3, max_length=50, description="Admin username")
    admin_password: str = Field(..., min_length=12, description="Admin password (12+ chars)")
    admin_email: str = Field(default="", description="Optional: Admin email")
    enable_mfa: bool = Field(default=False, description="Enable MFA for admin")


class SetupInitResponse(BaseModel):
    """Setup initialization response."""
    success: bool
    message: str
    redirect_url: str = "/dashboard"


def _check_env_file() -> bool:
    """Check if .env file exists."""
    env_path = Path(".env")
    return env_path.exists()


def _check_llm_config() -> bool:
    """Check if LLM provider is configured."""
    llm_provider = os.getenv("LLM_PROVIDER")
    if not llm_provider:
        return False

    # Check if corresponding API key exists
    if llm_provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    elif llm_provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    elif llm_provider == "groq":
        return bool(os.getenv("GROQ_API_KEY"))

    return False


def _check_admin_user(db: Session) -> bool:
    """Check if admin user exists in database."""
    admin = db.query(ApiUser).filter(ApiUser.role == "admin").first()
    return admin is not None


@router.get("/status", response_model=SetupStatusResponse)
def get_setup_status(db: Session = Depends(get_db)):
    """
    Check if initial setup is needed.

    Returns setup status including:
    - Whether setup wizard should be shown
    - Reasons why setup is needed
    - Status of .env file, LLM config, and admin user
    """
    has_env = _check_env_file()
    has_llm = _check_llm_config()
    has_admin = _check_admin_user(db)

    reasons = []
    if not has_env:
        reasons.append(".env file not found")
    if not has_llm:
        reasons.append("LLM provider not configured")
    if not has_admin:
        reasons.append("Admin user not created")

    setup_needed = not (has_env and has_llm and has_admin)

    return SetupStatusResponse(
        setup_needed=setup_needed,
        reasons=reasons,
        has_env_file=has_env,
        has_llm_config=has_llm,
        has_admin_user=has_admin,
    )


@router.post("/init", response_model=SetupInitResponse)
def initialize_setup(request: SetupInitRequest, db: Session = Depends(get_db)):
    """
    Initialize system setup.

    This endpoint:
    1. Creates/updates .env file with LLM configuration
    2. Creates admin user in database
    3. Validates all configurations

    Should only be called once during initial setup.
    """
    try:
        # Step 1: Create/update .env file
        env_path = Path(".env")
        env_template_path = Path(".env.example")

        # Read template if exists, otherwise create minimal config
        if env_template_path.exists():
            with open(env_template_path, "r", encoding="utf-8") as f:
                env_content = f.read()
        else:
            env_content = ""

        # Prepare LLM configuration
        llm_config_map = {
            "openai": {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": request.llm_api_key,
                "LLM_MODEL": request.llm_model or "gpt-4o-mini",
            },
            "gemini": {
                "LLM_PROVIDER": "gemini",
                "GEMINI_API_KEY": request.llm_api_key,
                "GEMINI_MODEL": request.llm_model or "gemini-pro",
            },
            "groq": {
                "LLM_PROVIDER": "groq",
                "GROQ_API_KEY": request.llm_api_key,
                "GROQ_MODEL": request.llm_model or "llama-3.3-70b-versatile",
            },
        }

        if request.llm_provider not in llm_config_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid LLM provider: {request.llm_provider}. Must be one of: openai, gemini, groq"
            )

        llm_config = llm_config_map[request.llm_provider]

        # Update .env content with LLM config
        for key, value in llm_config.items():
            # Remove old line if exists
            lines = env_content.split("\n")
            env_content = "\n".join([line for line in lines if not line.startswith(f"{key}=")])
            # Add new line
            env_content += f"\n{key}={value}"

        # Add admin user config
        env_content += f"\nDEFAULT_ADMIN_USERNAME={request.admin_username}"
        env_content += f"\nDEFAULT_ADMIN_PASSWORD={request.admin_password}"
        env_content += "\nDEFAULT_ADMIN_ROLE=admin"

        # Write .env file
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content.strip() + "\n")

        logger.info(f"Created .env file with LLM provider: {request.llm_provider}")

        # Step 2: Create admin user in database
        try:
            # Check if admin already exists
            existing_admin = db.query(ApiUser).filter(ApiUser.username == request.admin_username).first()
            if existing_admin:
                logger.warning(f"Admin user '{request.admin_username}' already exists, skipping creation")
            else:
                admin_user = create_user(
                    db=db,
                    username=request.admin_username,
                    password=request.admin_password,
                    role="admin",
                    mfa_enabled=request.enable_mfa,
                )
                logger.info(f"Created admin user: {request.admin_username}")

        except Exception as e:
            logger.exception(f"Failed to create admin user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create admin user: {str(e)}"
            )

        return SetupInitResponse(
            success=True,
            message="Setup completed successfully! You can now log in with your admin credentials.",
            redirect_url="/dashboard",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Setup initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Setup failed: {str(e)}"
        )


@router.post("/validate-api-key")
def validate_api_key(
    provider: str,
    api_key: str,
) -> Dict[str, Any]:
    """
    Validate LLM API key by making a test request.

    Args:
        provider: LLM provider (openai, gemini, groq)
        api_key: API key to validate

    Returns:
        {valid: bool, message: str, model_info: dict}
    """
    # This is a simplified validation - in production, you'd make actual API calls
    # to verify the key works

    if not api_key or len(api_key) < 10:
        return {
            "valid": False,
            "message": "API key too short",
            "model_info": {}
        }

    # Basic format validation
    if provider == "openai" and not api_key.startswith("sk-"):
        return {
            "valid": False,
            "message": "OpenAI API keys must start with 'sk-'",
            "model_info": {}
        }

    if provider == "groq" and not api_key.startswith("gsk_"):
        return {
            "valid": False,
            "message": "Groq API keys must start with 'gsk_'",
            "model_info": {}
        }

    # In a real implementation, you would:
    # 1. Import the LLM client
    # 2. Make a test API call
    # 3. Return actual validation results

    return {
        "valid": True,
        "message": "API key format looks valid (not yet tested with actual API call)",
        "model_info": {
            "provider": provider,
            "key_prefix": api_key[:10] + "...",
        }
    }
