"""
Control routes - start/stop/scale simulation.
"""
import os
import json
import logging
from typing import Optional, Dict, Any

import redis
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, Setting
from backend.api.dependencies import operator_dependencies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/control", tags=["Control"])

# ----------------------
# Redis util (optional)
# ----------------------
_redis_connection_pool: Optional[redis.ConnectionPool] = None
_redis_available = False


def _init_redis_pool() -> None:
    """Initialize Redis connection pool with health check."""
    global _redis_connection_pool, _redis_available

    url = os.getenv("REDIS_URL")
    if not url:
        logger.info("REDIS_URL not set; Redis features disabled (config sync, caching)")
        _redis_available = False
        return

    try:
        _redis_connection_pool = redis.ConnectionPool.from_url(
            url,
            decode_responses=True,
            max_connections=10,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        client = redis.Redis(connection_pool=_redis_connection_pool)
        client.ping()
        _redis_available = True
        logger.info("Redis connection established: %s", url.split("@")[-1] if "@" in url else url)
    except Exception as e:
        logger.warning(
            "Redis unavailable: %s. System will continue without Redis features (config sync, caching).",
            e
        )
        _redis_available = False
        _redis_connection_pool = None


def get_redis() -> Optional[redis.Redis]:
    """Get Redis client from pool if available."""
    if not _redis_available or not _redis_connection_pool:
        return None
    try:
        return redis.Redis(connection_pool=_redis_connection_pool)
    except Exception as e:
        logger.debug("Redis client creation failed: %s", e)
        return None


def publish_config_update(r: Optional[redis.Redis], payload: Dict[str, Any]):
    """Publish configuration update to Redis channel with fallback."""
    if not r:
        logger.debug("Redis unavailable; config update not published: %s", payload.get("type"))
        return
    try:
        r.publish("config_updates", json.dumps(payload))
        logger.debug("Config update published to Redis: %s", payload.get("type"))
    except Exception as e:
        logger.warning("Redis publish failed: %s. Config update skipped (not critical).", e)


def _set_setting(db: Session, key: str, value: Any):
    """Helper to create or update a setting in database."""
    row = db.query(Setting).filter(Setting.key == key).first()
    if not row:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    db.refresh(row)
    return row


# Initialize Redis pool at module level
_init_redis_pool()


class ScalePayload(BaseModel):
    factor: float = Field(1.0, gt=0)


@router.post("/start", dependencies=operator_dependencies)
def control_start(db: Session = Depends(get_db)):
    """Start the simulation (set simulation_active to True)."""
    _set_setting(db, "simulation_active", True)
    publish_config_update(get_redis(), {"type": "control", "simulation_active": True})
    return {"ok": True}


@router.post("/stop", dependencies=operator_dependencies)
def control_stop(db: Session = Depends(get_db)):
    """Stop the simulation (set simulation_active to False)."""
    _set_setting(db, "simulation_active", False)
    publish_config_update(get_redis(), {"type": "control", "simulation_active": False})
    return {"ok": True}


@router.post("/scale", dependencies=operator_dependencies)
def control_scale(
    factor: Optional[float] = Query(default=None, gt=0),
    body: Optional[ScalePayload] = Body(default=None),
    db: Session = Depends(get_db),
):
    """
    Scale the message rate by a factor.
    Can be provided via query param or request body.
    """
    resolved = factor
    if resolved is None and body is not None:
        resolved = body.factor
    if resolved is None:
        resolved = 1.0

    factor_value = float(resolved)
    if factor_value <= 0:
        raise HTTPException(400, "factor must be > 0")

    _set_setting(db, "scale_factor", factor_value)
    publish_config_update(get_redis(), {"type": "scale", "factor": factor_value})

    return {"ok": True, "factor": factor_value}
