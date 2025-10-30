"""
Metrics and system health check routes.
"""
import os
import sys
import time
import logging
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db, Bot, Chat, Message, Setting, SystemCheck, SessionLocal
from schemas import (
    MetricsResponse,
    SystemCheckCreate,
    SystemCheckResponse,
    SystemCheckSummaryBucket,
    SystemCheckSummaryResponse,
    SystemCheckSummaryInsight,
    SystemCheckSummaryRun,
)
from settings_utils import unwrap_setting_value
from backend.api.dependencies import viewer_dependencies, operator_dependencies

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Metrics & System Checks"])

APP_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # Go up to project root


def _unwrap_or_default(row: Optional[Setting], default: Any) -> Any:
    """Helper to unwrap setting value or return default."""
    if row is None:
        return default
    value = unwrap_setting_value(row.value)
    return default if value is None else value


def _as_bool(value: Any, default: bool = False) -> bool:
    """Convert value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def _as_float(value: Any, default: float) -> float:
    """Convert value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    """Convert value to integer."""
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _calculate_metrics(db: Session) -> MetricsResponse:
    """Calculate current system metrics."""
    total_bots = db.query(Bot).count()
    active_bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).count()
    total_chats = db.query(Chat).count()

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    last_hour_msgs = db.query(Message).filter(Message.created_at >= one_hour_ago).count()
    per_min = round(last_hour_msgs / 60.0, 3)

    sim_active_row = db.query(Setting).filter(Setting.key == "simulation_active").first()
    scale_row = db.query(Setting).filter(Setting.key == "scale_factor").first()
    rl_row = db.query(Setting).filter(Setting.key == "rate_limit_hits").first()
    tg429_row = db.query(Setting).filter(Setting.key == "telegram_429_count").first()
    tg5xx_row = db.query(Setting).filter(Setting.key == "telegram_5xx_count").first()

    sim_value = _unwrap_or_default(sim_active_row, False)
    scale_value = _unwrap_or_default(scale_row, 1.0)
    rl_value = _unwrap_or_default(rl_row, None)
    tg429_value = _unwrap_or_default(tg429_row, 0)
    tg5xx_value = _unwrap_or_default(tg5xx_row, 0)

    # Backward compatibility: if rate_limit_hits not present, use telegram_5xx_count
    rate_limit_hits = _as_int(rl_value, 0) if rl_value is not None else _as_int(tg5xx_value, 0)
    telegram_429_count = _as_int(tg429_value, 0)
    telegram_5xx_count = _as_int(tg5xx_value, 0)

    return MetricsResponse(
        total_bots=total_bots,
        active_bots=active_bots,
        total_chats=total_chats,
        messages_last_hour=last_hour_msgs,
        messages_per_minute=per_min,
        simulation_active=_as_bool(sim_value, False),
        scale_factor=_as_float(scale_value, 1.0),
        rate_limit_hits=rate_limit_hits,
        telegram_429_count=telegram_429_count,
        telegram_5xx_count=telegram_5xx_count,
    )


def _system_check_to_response(db_obj: SystemCheck) -> SystemCheckResponse:
    """Convert SystemCheck model to response schema."""
    details = db_obj.details or {}
    steps = details.get("steps", [])
    health_checks = details.get("health_checks", [])
    return SystemCheckResponse(
        id=db_obj.id,
        status=db_obj.status,
        total_steps=db_obj.total_steps,
        passed_steps=db_obj.passed_steps,
        failed_steps=db_obj.failed_steps,
        duration=db_obj.duration,
        triggered_by=db_obj.triggered_by,
        steps=steps,
        health_checks=health_checks,
        created_at=db_obj.created_at,
    )


def _run_step(name: str, cmd: List[str], env: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a command as a system check step."""
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(APP_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    duration = time.time() - started
    return {
        "name": name,
        "success": proc.returncode == 0,
        "duration": duration,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


@router.get("/metrics", response_model=MetricsResponse, dependencies=viewer_dependencies)
def metrics(db: Session = Depends(get_db)):
    """Get current system metrics."""
    return _calculate_metrics(db)


@router.get("/queue/stats", dependencies=viewer_dependencies)
def queue_stats():
    """
    Get message queue statistics.

    Returns current queue lengths for each priority level.
    """
    try:
        from behavior_engine import _ENGINE

        if _ENGINE is None:
            return {
                "error": "Behavior engine not running",
                "stats": None
            }

        stats = _ENGINE.msg_queue.get_stats()
        return {
            "stats": stats,
            "total_queued": sum(stats.values()) - stats.get("dlq", 0),
            "total_failed": stats.get("dlq", 0),
        }
    except Exception as e:
        logger.exception("Error getting queue stats: %s", e)
        return {
            "error": str(e),
            "stats": None
        }


@router.post("/system/checks", response_model=SystemCheckResponse, status_code=status.HTTP_201_CREATED, dependencies=operator_dependencies)
def create_system_check(payload: SystemCheckCreate, db: Session = Depends(get_db)):
    """Create a system check record (for external test runners)."""
    db_obj = SystemCheck(
        status=payload.status,
        total_steps=payload.total_steps,
        passed_steps=payload.passed_steps,
        failed_steps=payload.failed_steps,
        duration=payload.duration,
        triggered_by=payload.triggered_by,
        details={
            "steps": [step.dict() for step in payload.steps],
            "health_checks": [hc.dict() for hc in payload.health_checks],
        },
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return _system_check_to_response(db_obj)


@router.get("/system/checks/latest", response_model=Optional[SystemCheckResponse], dependencies=viewer_dependencies)
def get_latest_system_check(db: Session = Depends(get_db)):
    """Get the most recent system check."""
    obj = (
        db.query(SystemCheck)
        .order_by(SystemCheck.created_at.desc())
        .first()
    )
    if not obj:
        return None
    return _system_check_to_response(obj)


@router.get(
    "/system/checks/summary",
    response_model=SystemCheckSummaryResponse,
    dependencies=viewer_dependencies,
)
def get_system_check_summary(
    window_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Get system check summary over a time window.

    Provides aggregated statistics, daily breakdown, insights, and recommended actions.
    """
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=window_days)

    checks = (
        db.query(SystemCheck)
        .filter(SystemCheck.created_at >= window_start)
        .order_by(SystemCheck.created_at.asc())
        .all()
    )

    total_runs = len(checks)
    passed_runs = sum(1 for check in checks if check.status.lower() == "passed")
    failed_runs = total_runs - passed_runs
    durations = [check.duration for check in checks if check.duration is not None]
    average_duration = round(sum(durations) / len(durations), 2) if durations else None
    last_run_at = checks[-1].created_at if checks else None

    # Daily breakdown
    per_day: Dict[Any, Dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    for check in checks:
        bucket = per_day[check.created_at.date()]
        bucket["total"] += 1
        if check.status.lower() == "passed":
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    daily_breakdown = [
        SystemCheckSummaryBucket(
            date=day,
            total=data["total"],
            passed=data["passed"],
            failed=data["failed"],
        )
        for day, data in sorted(per_day.items())
    ]

    # Recent runs
    recent_runs = [
        SystemCheckSummaryRun(
            id=check.id,
            status=check.status,
            created_at=check.created_at,
            duration=check.duration,
            triggered_by=check.triggered_by,
            total_steps=check.total_steps,
            passed_steps=check.passed_steps,
            failed_steps=check.failed_steps,
        )
        for check in sorted(checks, key=lambda record: record.created_at, reverse=True)[:5]
    ]

    success_rate = round(passed_runs / total_runs, 4) if total_runs else 0.0

    # Generate insights and recommended actions
    insight_messages: Set[str] = set()
    insights: List[SystemCheckSummaryInsight] = []
    recommended_actions: List[str] = []

    def add_insight(level: str, message: str) -> None:
        if not message or message in insight_messages:
            return
        insights.append(SystemCheckSummaryInsight(level=level, message=message))
        insight_messages.add(message)

    def add_action(text: str) -> None:
        if not text:
            return
        if text not in recommended_actions:
            recommended_actions.append(text)

    overall_status: str = "empty" if total_runs == 0 else "healthy"
    overall_message = (
        f"Son {window_days} gün içinde otomasyon testi kaydı bulunmuyor."
        if total_runs == 0
        else "Otomasyon koşuları sağlıklı görünüyor."
    )

    def update_status(level: str, message: Optional[str] = None) -> None:
        nonlocal overall_status, overall_message
        priority = {"empty": 0, "healthy": 1, "warning": 2, "critical": 3}
        if priority.get(level, 0) > priority.get(overall_status, 0):
            overall_status = level
            if message:
                overall_message = message
        elif level == overall_status and message:
            overall_message = message

    now = datetime.now(timezone.utc)
    hours_since_last_run: Optional[float] = None
    if last_run_at is not None:
        if last_run_at.tzinfo is None:
            last_run_at = last_run_at.replace(tzinfo=timezone.utc)
        hours_since_last_run = (now - last_run_at).total_seconds() / 3600.0

    if total_runs == 0:
        add_insight("info", "Henüz otomasyon raporu oluşmamış. İlk testi çalıştırın.")
        add_action("Panelden \"Testleri çalıştır\" butonunu kullanarak ilk kontrolü başlatın.")
    else:
        if failed_runs > 0:
            failure_ratio = failed_runs / total_runs
            severity = "critical" if failure_ratio >= 0.3 or success_rate < 0.7 else "warning"
            message = (
                "Testlerin önemli bir kısmı başarısız; aksiyon alınmalı."
                if severity == "critical"
                else "Bazı otomasyon adımları başarısız sonuçlandı."
            )
            update_status(severity, message)
            add_insight(
                severity,
                f"Son {total_runs} koşunun {failed_runs} tanesi başarısız oldu (başarı oranı %{round(success_rate * 100, 1)}).",
            )
            add_action("Hata veren adımların loglarını inceleyip testleri yeniden çalıştırın.")
        else:
            add_insight("success", "Son otomasyon koşularının tamamı başarılı tamamlandı.")

        if failed_runs == 0 and success_rate >= 0.95:
            add_insight("success", "Başarı oranı %{:.1f} ile hedef seviyede.".format(success_rate * 100))
        elif failed_runs == 0:
            add_insight("info", "Başarı oranı %{:.1f} seviyesinde.".format(success_rate * 100))

        if average_duration is not None:
            if average_duration > 20:
                update_status("warning", "Test süreleri uzamış görünüyor; altyapıyı kontrol edin.")
                add_insight(
                    "warning",
                    f"Ortalama test süresi {average_duration:.1f} sn; bu değer önceki günlerden yüksek olabilir.",
                )
                add_action("Uzun süren adımların loglarını inceleyin ve gerekli optimizasyonları planlayın.")
            elif failed_runs == 0:
                add_insight("success", f"Ortalama test süresi {average_duration:.1f} sn ile sağlıklı görünüyor.")

        if hours_since_last_run is not None:
            if hours_since_last_run > 24:
                update_status("critical", "Son otomasyon koşusu 24 saatten eski; yeni bir koşu başlatın.")
                add_insight("critical", "Son otomasyon koşusu 24 saatten daha eski.")
                add_action("Güncel sonuç almak için otomasyon testlerini yeniden başlatın.")
            elif hours_since_last_run > 12:
                update_status("warning", "Son otomasyon koşusu 12 saatten eski; yeni koşu planlayın.")
                add_insight("warning", "Son otomasyon koşusu 12 saatten daha eski.")
                add_action("Testleri manuel olarak tetikleyin veya zamanlayıcıyı gözden geçirin.")
            elif failed_runs == 0:
                add_insight("success", "Son otomasyon koşusu son 12 saat içinde tamamlandı.")

    if overall_status == "healthy" and not insights:
        add_insight("success", "Otomasyon koşuları stabil şekilde çalışıyor.")

    return SystemCheckSummaryResponse(
        window_start=window_start,
        window_end=window_end,
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        success_rate=success_rate,
        average_duration=average_duration,
        last_run_at=last_run_at,
        daily_breakdown=daily_breakdown,
        overall_status=overall_status,
        overall_message=overall_message,
        insights=insights,
        recommended_actions=recommended_actions,
        recent_runs=recent_runs,
    )


@router.post("/system/checks/run", response_model=SystemCheckResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=operator_dependencies)
def run_system_checks(db: Session = Depends(get_db)):
    """
    Run automated system checks (preflight, pytest, stress test).

    This endpoint executes tests asynchronously and returns immediately with results.
    """
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    env.setdefault("API_BASE", os.getenv("API_BASE", "http://localhost:8000"))

    steps = [
        _run_step("preflight", [sys.executable, "preflight.py"], env=env),
        _run_step(
            "pytest",
            [sys.executable, "-m", "pytest", "-q", "tests/test_api_flows.py", "tests/test_content_filters.py"],
            env=env,
        ),
        _run_step(
            "stress-test",
            [
                sys.executable,
                "scripts/stress_test.py",
                "--duration",
                os.getenv("SYSTEM_CHECK_STRESS_DURATION", "15"),
                "--concurrency",
                os.getenv("SYSTEM_CHECK_STRESS_CONCURRENCY", "2"),
            ],
            env=env,
        ),
    ]

    total = len(steps)
    passed = sum(1 for step in steps if step["success"])
    failed = total - passed
    total_duration = sum(step["duration"] for step in steps)
    status_value = "passed" if failed == 0 else "failed"

    db_obj = SystemCheck(
        status=status_value,
        total_steps=total,
        passed_steps=passed,
        failed_steps=failed,
        duration=total_duration,
        triggered_by="dashboard",
        details={"steps": steps, "health_checks": []},
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    return _system_check_to_response(db_obj)
