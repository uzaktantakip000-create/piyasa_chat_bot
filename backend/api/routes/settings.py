"""
Settings routes - global system configuration.
"""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, AnyHttpUrl, ValidationError, parse_obj_as
from sqlalchemy.orm import Session

from database import get_db, Setting
from schemas import SettingResponse
from settings_utils import normalize_message_length_profile
from backend.api.dependencies import viewer_dependencies, admin_dependencies
from backend.api.routes.control import get_redis, publish_config_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])


def _normalize_setting_value(key: str, raw: Any) -> Dict[str, Any]:
    """Normalize setting value to standard format."""
    if key == "message_length_profile":
        normalized = normalize_message_length_profile(raw)
        return {"value": normalized}
    if isinstance(raw, dict) and "value" in raw and len(raw) == 1:
        return raw
    return {"value": raw}


def _setting_to_response(row: Setting) -> SettingResponse:
    """Convert Setting model to response schema."""
    return SettingResponse(
        key=row.key,
        value=_normalize_setting_value(row.key, row.value),
        updated_at=row.updated_at,
    )


def _normalize_news_feed_urls(value: Any) -> List[str]:
    """Validate and normalize news feed URLs."""
    if isinstance(value, dict) and "value" in value and len(value) == 1:
        value = value["value"]

    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        raise HTTPException(status_code=400, detail="news_feed_urls değeri liste olmalıdır.")

    normalized: List[str] = []
    for item in candidates:
        item_str = str(item or "").strip()
        if not item_str:
            continue
        try:
            parsed = parse_obj_as(AnyHttpUrl, item_str)
        except ValidationError:
            raise HTTPException(status_code=400, detail=f"Geçersiz RSS adresi: {item_str}")
        parsed_str = str(parsed)
        if parsed_str not in normalized:
            normalized.append(parsed_str)

    return normalized


class SettingsBulkUpdate(BaseModel):
    updates: Dict[str, Any] = Field(default_factory=dict)


class SettingUpdate(BaseModel):
    value: Any


@router.get("", response_model=List[SettingResponse], dependencies=viewer_dependencies)
def list_settings(db: Session = Depends(get_db)):
    """Get all system settings."""
    rows = db.query(Setting).order_by(Setting.key.asc()).all()
    return [_setting_to_response(row) for row in rows]


@router.put("/bulk", response_model=List[SettingResponse], dependencies=admin_dependencies)
def update_settings_bulk(body: SettingsBulkUpdate, db: Session = Depends(get_db)):
    """
    Bulk update multiple settings at once.
    Requires admin role.
    """
    if not body.updates:
        raise HTTPException(400, "No updates provided")

    changed: List[str] = []
    out: List[Setting] = []

    for k, v in body.updates.items():
        # Normalize special settings
        if k == "message_length_profile":
            v = normalize_message_length_profile(v)
        if k == "news_feed_urls":
            v = _normalize_news_feed_urls(v)

        row = db.query(Setting).filter(Setting.key == k).first()
        if not row:
            row = Setting(key=k, value=v)
            db.add(row)
        else:
            row.value = v
        changed.append(k)
        out.append(row)

    db.commit()
    for row in out:
        db.refresh(row)

    publish_config_update(get_redis(), {"type": "settings_updated", "keys": changed})

    return [_setting_to_response(row) for row in out]


@router.patch("/{key}", response_model=SettingResponse, dependencies=admin_dependencies)
def update_setting(key: str, payload: SettingUpdate, db: Session = Depends(get_db)):
    """
    Update a single setting by key.
    Requires admin role.
    """
    value = payload.value

    # Normalize special settings
    if key == "message_length_profile":
        value = normalize_message_length_profile(value)
    if key == "news_feed_urls":
        value = _normalize_news_feed_urls(value)

    row = db.query(Setting).filter(Setting.key == key).first()
    if not row:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value

    db.commit()
    db.refresh(row)

    publish_config_update(get_redis(), {"type": "settings_updated", "keys": [key]})

    return _setting_to_response(row)
