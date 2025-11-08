"""
System routes - System checks and health monitoring.
"""
import os
import sys
import time
import logging
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db, SystemCheck
from schemas import (
    SystemCheckCreate,
    SystemCheckResponse,
    SystemCheckSummaryResponse,
    SystemCheckSummaryBucket,
    SystemCheckSummaryRun,
    SystemCheckSummaryInsight,
)
from backend.api.dependencies import viewer_dependencies, operator_dependencies

logger = logging.getLogger(__name__)

APP_ROOT = Path(__file__).resolve().parent.parent.parent

router = APIRouter(prefix="/system", tags=["System"])


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
    """Execute a system check step via subprocess."""
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


# ============================================================================
# System Checks Endpoints
# ============================================================================

@router.post("/checks", response_model=SystemCheckResponse, status_code=status.HTTP_201_CREATED, dependencies=operator_dependencies)
def create_system_check(payload: SystemCheckCreate, db: Session = Depends(get_db)):
    """
    Create a new system check record.
    Requires operator role.
    """
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


@router.get("/checks/latest", response_model=Optional[SystemCheckResponse], dependencies=viewer_dependencies)
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
    "/checks/summary",
    response_model=SystemCheckSummaryResponse,
    dependencies=viewer_dependencies,
)
def get_system_check_summary(
    window_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Get system checks summary for the last N days.
    Includes daily breakdown, insights, and recommended actions.
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

    per_day = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
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

    insight_messages = set()
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
        # Ensure last_run_at is timezone-aware for comparison
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


@router.post("/checks/run", response_model=SystemCheckResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=operator_dependencies)
def run_system_checks(db: Session = Depends(get_db)):
    """
    Run system checks (preflight, pytest, stress test).
    Requires operator role.
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


# ============================================================================
# Enhanced Health Dashboard Endpoint
# ============================================================================

@router.get("/health", dependencies=viewer_dependencies)
def get_system_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get comprehensive system health status for dashboard.

    Returns real-time status of:
    - API service
    - Worker service
    - Database
    - Redis (optional)
    - Disk usage
    - System alerts

    Requires viewer role or higher.
    """
    import psutil
    from database import Message, Bot

    health = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api": {},
        "worker": {},
        "database": {},
        "redis": {},
        "disk": {},
        "alerts": []
    }

    # API Status
    try:
        import main
        health["api"] = {
            "status": "running",
            "uptime_seconds": time.time() - getattr(main, '_start_time', time.time()),
            "version": getattr(main, '__version__', "unknown"),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
    except Exception as e:
        logger.error(f"Failed to get API status: {e}")
        health["api"] = {"status": "error", "error": str(e)}

    # Worker Status
    try:
        # Check last message timestamp
        last_message = db.query(Message).order_by(Message.timestamp.desc()).first()

        if last_message:
            last_message_age = (datetime.now(timezone.utc) - last_message.timestamp.replace(tzinfo=timezone.utc)).total_seconds()
            worker_status = "active" if last_message_age < 300 else "slow"  # 5 minutes threshold
        else:
            worker_status = "idle"
            last_message_age = None

        # Count messages in last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        messages_last_hour = db.query(Message).filter(
            Message.timestamp >= one_hour_ago
        ).count()

        health["worker"] = {
            "status": worker_status,
            "last_message_age_seconds": last_message_age,
            "messages_last_hour": messages_last_hour,
            "last_message_at": last_message.timestamp.isoformat() if last_message else None,
        }

        # Alert if worker is slow
        if worker_status == "slow":
            health["alerts"].append({
                "severity": "warning",
                "component": "worker",
                "message": f"No messages generated in last {int(last_message_age/60)} minutes"
            })

    except Exception as e:
        logger.error(f"Failed to get worker status: {e}")
        health["worker"] = {"status": "error", "error": str(e)}

    # Database Status
    try:
        # Test connection
        db.execute("SELECT 1")

        # Count active bots
        active_bots = db.query(Bot).filter(Bot.is_enabled == True).count()
        total_messages = db.query(Message).count()

        health["database"] = {
            "status": "connected",
            "type": "sqlite" if "sqlite" in str(db.bind.url) else "postgresql",
            "active_bots": active_bots,
            "total_messages": total_messages,
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health["database"] = {"status": "error", "error": str(e)}
        health["alerts"].append({
            "severity": "critical",
            "component": "database",
            "message": f"Database connection failed: {str(e)}"
        })

    # Redis Status (optional)
    try:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            from backend.caching.redis_cache import RedisCache
            redis_client = RedisCache()
            if redis_client.is_available():
                health["redis"] = {
                    "status": "connected",
                    "available": True,
                }
            else:
                health["redis"] = {"status": "unavailable", "available": False}
        else:
            health["redis"] = {"status": "not_configured", "available": False}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health["redis"] = {"status": "error", "error": str(e), "available": False}

    # Disk Usage
    try:
        disk = psutil.disk_usage('.')
        disk_usage_percent = disk.percent

        health["disk"] = {
            "usage_percent": disk_usage_percent,
            "free_gb": disk.free / (1024**3),
            "total_gb": disk.total / (1024**3),
        }

        # Alert if disk is >90% full
        if disk_usage_percent > 90:
            health["alerts"].append({
                "severity": "critical",
                "component": "disk",
                "message": f"Disk usage critical: {disk_usage_percent:.1f}% full"
            })
        elif disk_usage_percent > 80:
            health["alerts"].append({
                "severity": "warning",
                "component": "disk",
                "message": f"Disk usage high: {disk_usage_percent:.1f}% full"
            })

    except Exception as e:
        logger.error(f"Disk usage check failed: {e}")
        health["disk"] = {"error": str(e)}

    # Overall status
    critical_errors = [a for a in health["alerts"] if a.get("severity") == "critical"]
    health["overall_status"] = "critical" if critical_errors else "healthy"

    return health
