from __future__ import annotations

import argparse
import atexit
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def stream_output(name: str, proc: subprocess.Popen) -> None:
    """Stream process output with a prefix so the user can follow logs."""
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").rstrip()
        print(f"[{name}] {text}")


def spawn_process(name: str, cmd: List[str], cwd: Optional[Path] = None) -> subprocess.Popen:
    """Start a subprocess and start a background thread to stream its output."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    t = threading.Thread(target=stream_output, args=(name, proc), daemon=True)
    t.start()
    return proc


def wait_for_api(base_url: str, timeout: int = 60) -> bool:
    """Poll the FastAPI /healthz endpoint until it responds or timeout."""
    start = time.time()
    url = f"{base_url.rstrip('/')}/healthz"
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=5)
            if resp.ok and resp.json().get("ok"):
                print(f"[oneclick] API hazır: {url}")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_ui(port: str, timeout: int = 60) -> bool:
    """Poll the Vite dev server until it responds or timeout."""
    start = time.time()
    url = f"http://localhost:{port}"
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code < 500:
                print(f"[oneclick] UI hazır: {url}")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _health_result(name: str, ok: Optional[bool], detail: str) -> HealthCheckResult:
    if ok is None:
        status = "skipped"
    else:
        status = "healthy" if ok else "unhealthy"
    return HealthCheckResult(name=name, status=status, detail=detail)


def collect_health_checks(
    api_base: str,
    api_key: Optional[str],
    redis_url: Optional[str],
    processes: Dict[str, subprocess.Popen],
    skip_worker: bool,
    skip_ui: bool,
    ui_port: str,
) -> List[HealthCheckResult]:
    results: List[HealthCheckResult] = []

    # API health
    try:
        resp = requests.get(f"{api_base.rstrip('/')}/healthz", timeout=10)
        ok = resp.ok and resp.json().get("ok")
        detail = f"{resp.status_code} {resp.reason}"
        results.append(_health_result("api", ok, detail))
    except Exception as exc:
        results.append(_health_result("api", False, str(exc)))

    # Database health via /settings (requires API key)
    if api_key:
        try:
            headers = {"X-API-Key": api_key}
            resp = requests.get(f"{api_base.rstrip('/')}/settings", headers=headers, timeout=15)
            ok = resp.ok
            count = len(resp.json()) if ok else 0
            detail = f"{count} ayar kaydı" if ok else f"{resp.status_code}"
            results.append(_health_result("database", ok, detail))
        except Exception as exc:
            results.append(_health_result("database", False, str(exc)))
    else:
        results.append(_health_result("database", None, "API_KEY tanımlı değil"))

    # Redis health
    if redis_url:
        try:
            import redis  # type: ignore

            client = redis.from_url(redis_url)
            pong = client.ping()
            results.append(_health_result("redis", bool(pong), "PING yanıtı"))
        except Exception as exc:
            results.append(_health_result("redis", False, str(exc)))
    else:
        results.append(_health_result("redis", None, "REDIS_URL tanımlı değil"))

    # Worker process health
    if skip_worker:
        results.append(_health_result("worker", None, "skip_worker parametresi"))
    else:
        worker_proc = processes.get("worker")
        if worker_proc and worker_proc.poll() is None:
            results.append(_health_result("worker", True, f"PID={worker_proc.pid}"))
        else:
            exit_code = worker_proc.returncode if worker_proc else "başlatılamadı"
            results.append(_health_result("worker", False, f"Durum: {exit_code}"))

    # UI health
    if skip_ui:
        results.append(_health_result("ui", None, "skip_ui parametresi"))
    else:
        try:
            resp = requests.get(f"http://localhost:{ui_port}", timeout=10)
            ok = resp.status_code < 500
            detail = f"{resp.status_code} {resp.reason}"
            results.append(_health_result("ui", ok, detail))
        except Exception as exc:
            results.append(_health_result("ui", False, str(exc)))

    return results


def print_health_summary(results: List[HealthCheckResult]) -> None:
    if not results:
        return
    print("\n[oneclick] Sağlık Kontrolü Özeti:")
    for item in results:
        if item.status == "healthy":
            badge = "OK"
        elif item.status == "skipped":
            badge = "ATLANDI"
        else:
            badge = "HATA"
        detail = f" - {item.detail}" if item.detail else ""
        print(f"  • {item.name}: {badge}{detail}")


def ensure_env_file() -> None:
    """Create a .env file from .env.example if it does not exist."""
    env_path = ROOT / ".env"
    if env_path.exists():
        return

    example = ROOT / ".env.example"
    if not example.exists():
        print("[oneclick] Uyarı: .env bulunamadı ve .env.example mevcut değil.")
        return

    env_path.write_text(example.read_text(), encoding="utf-8")
    print("[oneclick] .env dosyası .env.example'dan kopyalandı. Lütfen gerekli alanları güncelleyin.")


@dataclass
class StepResult:
    name: str
    success: bool
    duration: float
    stdout: str
    stderr: str


@dataclass
class HealthCheckResult:
    name: str
    status: str
    detail: str


def run_command(name: str, cmd: List[str], cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> StepResult:
    print(f"[oneclick] {name} çalıştırılıyor: {' '.join(cmd)}")
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
    )
    duration = time.time() - started
    success = proc.returncode == 0
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip())
    status = "BAŞARILI" if success else "HATALI"
    print(f"[oneclick] {name} tamamlandı → {status} ({duration:.1f}s)")
    return StepResult(name=name, success=success, duration=duration, stdout=proc.stdout, stderr=proc.stderr)


def run_preflight(api_base: str) -> StepResult:
    env = os.environ.copy()
    env["API_BASE"] = api_base
    return run_command("preflight", [sys.executable, "preflight.py"], cwd=ROOT, env=env)


def run_pytest() -> StepResult:
    return run_command(
        "pytest",
        [sys.executable, "-m", "pytest", "-q", "tests/test_api_flows.py", "tests/test_content_filters.py"],
        cwd=ROOT,
    )


def run_docs_tests() -> StepResult:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    return run_command(
        "docs-tests",
        [sys.executable, "-m", "pytest", "-q", "tests/test_quickstart_readme.py"],
        cwd=ROOT,
        env=env,
    )


def run_stress(duration: int = 30, concurrency: int = 2) -> StepResult:
    return run_command(
        "stress-test",
        [
            sys.executable,
            "scripts/stress_test.py",
            "--duration",
            str(duration),
            "--concurrency",
            str(concurrency),
        ],
        cwd=ROOT,
    )


def parse_args() -> Dict[str, str]:
    parser = argparse.ArgumentParser(description="Tek komutla API, worker ve paneli başlat.")
    parser.add_argument("--api-host", default="0.0.0.0", help="FastAPI host (varsayılan: 0.0.0.0)")
    parser.add_argument("--api-port", default="8000", help="FastAPI port (varsayılan: 8000)")
    parser.add_argument("--ui-port", default="5173", help="Vite port (varsayılan: 5173)")
    parser.add_argument("--skip-ui", action="store_true", help="Ön yüzü başlatma")
    parser.add_argument("--skip-worker", action="store_true", help="Worker sürecini başlatma")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Sağlık kontrolü için API adresi")
    args = parser.parse_args()

    return {
        "api_host": args.api_host,
        "api_port": str(args.api_port),
        "ui_port": str(args.ui_port),
        "skip_ui": str(args.skip_ui),
        "skip_worker": str(args.skip_worker),
        "api_base": args.api_base,
    }


def main() -> None:
    ensure_env_file()
    load_dotenv(dotenv_path=ROOT / ".env")

    args = parse_args()
    api_host = args["api_host"]
    api_port = args["api_port"]
    ui_port = args["ui_port"]
    skip_ui = args["skip_ui"] == "True"
    skip_worker = args["skip_worker"] == "True"
    api_base = args["api_base"]

    processes: Dict[str, subprocess.Popen] = {}

    def shutdown_all() -> None:
        for proc in processes.values():
            if proc.poll() is None:
                try:
                    proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()

    atexit.register(shutdown_all)

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        api_host,
        "--port",
        api_port,
    ]
    print("[oneclick] FastAPI başlatılıyor...")
    processes["api"] = spawn_process("api", api_cmd, cwd=ROOT)

    if not skip_worker:
        worker_cmd = [sys.executable, "worker.py"]
        print("[oneclick] Worker başlatılıyor...")
        processes["worker"] = spawn_process("worker", worker_cmd, cwd=ROOT)

    if not skip_ui:
        ui_cmd = ["npm", "run", "dev", "--", "--port", ui_port, "--host", "0.0.0.0"]
        print("[oneclick] Panel (Vite) başlatılıyor...")
        processes["ui"] = spawn_process("ui", ui_cmd, cwd=ROOT)

    step_results: List[StepResult] = []
    health_checks: List[HealthCheckResult] = []

    if wait_for_api(api_base):
        if not skip_ui:
            wait_for_ui(ui_port)
        health_checks = collect_health_checks(
            api_base=api_base,
            api_key=os.getenv("API_KEY"),
            redis_url=os.getenv("REDIS_URL"),
            processes=processes,
            skip_worker=skip_worker,
            skip_ui=skip_ui,
            ui_port=ui_port,
        )
        print_health_summary(health_checks)
        step_results.append(run_preflight(api_base))
        step_results.append(run_pytest())
        step_results.append(run_docs_tests())
        step_results.append(run_stress())
        print("[oneclick] Sistem hazır. Yönetim paneli için tarayıcıdan http://localhost:" + ui_port + " adresine gidin.")
    else:
        print("[oneclick] Uyarı: API belirtilen sürede yanıt vermedi.")

    print("[oneclick] Çıkmak için Ctrl+C tuşlayın. Alt süreçler otomatik kapatılacak.")

    try:
        while any(proc.poll() is None for proc in processes.values()):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[oneclick] Kapatılıyor...")
    finally:
        if step_results or health_checks:
            report = {
                "generated_at": time.time(),
                "steps": [asdict(step) for step in step_results],
                "health_checks": [asdict(item) for item in health_checks],
            }
            report_path = ROOT / "latest_oneclick_report.json"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"[oneclick] Özet rapor kaydedildi: {report_path}")
            send_report_to_api(api_base, step_results, health_checks)

        shutdown_all()


def send_report_to_api(api_base: str, steps: List[StepResult], health_checks: List[HealthCheckResult]) -> None:
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("[oneclick] API_KEY bulunamadı; sonuçlar API'ye gönderilmeyecek.")
        return

    total = len(steps)
    passed = sum(1 for step in steps if step.success)
    failed = total - passed
    total_duration = sum(step.duration for step in steps)
    status = "passed" if failed == 0 else "failed"
    if any(hc.status == "unhealthy" for hc in health_checks):
        status = "failed"

    payload = {
        "status": status,
        "total_steps": total,
        "passed_steps": passed,
        "failed_steps": failed,
        "duration": round(total_duration, 2) if total_duration else None,
        "triggered_by": "oneclick",
        "steps": [
            {
                "name": step.name,
                "success": step.success,
                "duration": round(step.duration, 2),
                "stdout": step.stdout,
                "stderr": step.stderr,
            }
            for step in steps
        ],
        "health_checks": [
            {
                "name": hc.name,
                "status": hc.status,
                "detail": hc.detail,
            }
            for hc in health_checks
        ],
    }

    url = f"{api_base.rstrip('/')}/system/checks"
    try:
        resp = requests.post(url, json=payload, headers={"X-API-Key": api_key}, timeout=20)
        if resp.ok:
            print("[oneclick] Test sonuçları API'ye kaydedildi.")
        else:
            print(f"[oneclick] Test sonuçları kaydedilemedi: {resp.status_code} {resp.text}")
    except Exception as exc:
        print(f"[oneclick] Test sonuçları gönderilirken hata oluştu: {exc}")


if __name__ == "__main__":
    main()
