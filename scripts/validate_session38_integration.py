"""
Session 38 Integration Validation Script

Bu script, Session 38'de yapılan tüm değişikliklerin
gerçekten entegre olduğunu ve çalıştığını doğrular.

Çalıştırma:
    python scripts/validate_session38_integration.py

Kontroller:
    1. LLM Batch Client Tests (7 tests)
    2. Behavior Engine Import
    3. Batch Methods Existence
    4. Database Settings
    5. Monitoring Files
    6. Grafana Dashboard
"""

import sys
import os
from pathlib import Path

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_section(title):
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

def print_ok(message):
    print(f"{GREEN}[OK]{RESET} {message}")

def print_fail(message):
    print(f"{RED}[FAIL]{RESET} {message}")

def print_warn(message):
    print(f"{YELLOW}[WARN]{RESET} {message}")

def check_batch_client_tests():
    """Run LLM batch client tests"""
    print_section("1. LLM Batch Client Tests")

    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/test_llm_batch.py", "-v", "-o", "addopts="],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        # Count passed tests
        passed = result.stdout.count("PASSED")
        print_ok(f"All {passed}/7 tests passed")
        return True
    else:
        print_fail("Some tests failed")
        print(result.stdout)
        return False

def check_behavior_engine_import():
    """Check if BehaviorEngine can be imported"""
    print_section("2. Behavior Engine Import")

    try:
        from behavior_engine import BehaviorEngine
        print_ok("BehaviorEngine import successful")
        return True
    except Exception as e:
        print_fail(f"Import failed: {e}")
        return False

def check_batch_methods():
    """Check if batch processing methods exist"""
    print_section("3. Batch Processing Methods")

    try:
        from behavior_engine import BehaviorEngine
        import inspect

        engine = BehaviorEngine.__dict__

        methods = [
            '_check_priority_queue_batch',
            '_process_priority_queue_batch',
        ]

        all_ok = True
        for method_name in methods:
            if method_name in engine and callable(engine[method_name]):
                sig = inspect.signature(engine[method_name])
                print_ok(f"{method_name}{sig}")
            else:
                print_fail(f"{method_name} - NOT FOUND")
                all_ok = False

        # Check llm_batch initialization
        init_source = inspect.getsource(BehaviorEngine.__init__)
        if 'LLMBatchClient' in init_source:
            print_ok("__init__ initializes llm_batch")
        else:
            print_fail("llm_batch not initialized in __init__")
            all_ok = False

        return all_ok
    except Exception as e:
        print_fail(f"Method check failed: {e}")
        return False

def check_database_settings():
    """Check if batch settings exist in database"""
    print_section("4. Database Settings")

    try:
        from database import SessionLocal, Setting, init_default_settings

        # Ensure settings are initialized
        init_default_settings()

        db = SessionLocal()
        try:
            batch_enabled = db.query(Setting).filter(Setting.key == 'batch_processing_enabled').first()
            batch_size = db.query(Setting).filter(Setting.key == 'batch_size').first()

            all_ok = True
            if batch_enabled:
                print_ok(f"batch_processing_enabled: {batch_enabled.value}")
            else:
                print_fail("batch_processing_enabled NOT FOUND")
                all_ok = False

            if batch_size:
                print_ok(f"batch_size: {batch_size.value}")
            else:
                print_fail("batch_size NOT FOUND")
                all_ok = False

            total = db.query(Setting).count()
            print_ok(f"Total settings in database: {total}")

            return all_ok
        finally:
            db.close()
    except Exception as e:
        print_fail(f"Database check failed: {e}")
        return False

def check_monitoring_files():
    """Check if monitoring stack files exist"""
    print_section("5. Monitoring Stack Files")

    files = [
        ('monitoring/prometheus.yml', 'Prometheus Config'),
        ('monitoring/alertmanager/alertmanager.yml', 'AlertManager Config'),
        ('monitoring/prometheus_rules/alert_rules.yml', 'Alert Rules'),
        ('monitoring/grafana/provisioning/dashboards/piyasa_chatbot_overview.json', 'Grafana Dashboard'),
        ('docs/LLM_BATCH_GENERATION_GUIDE.md', 'Batch Guide'),
        ('docs/MONITORING_INTEGRATION_GUIDE.md', 'Monitoring Guide'),
    ]

    all_ok = True
    for file_path, description in files:
        if Path(file_path).exists():
            size = Path(file_path).stat().st_size
            lines = len(Path(file_path).read_text(encoding='utf-8', errors='ignore').splitlines())
            print_ok(f"{description}: {lines} lines, {size} bytes")
        else:
            print_fail(f"{description}: NOT FOUND ({file_path})")
            all_ok = False

    return all_ok

def check_grafana_dashboard():
    """Check Grafana dashboard structure"""
    print_section("6. Grafana Dashboard")

    try:
        import json
        with open('monitoring/grafana/provisioning/dashboards/piyasa_chatbot_overview.json', encoding='utf-8') as f:
            dashboard = json.load(f)

        panels = dashboard.get('panels', [])
        print_ok(f"Total panels: {len(panels)}")

        # Expected: 18+ panels
        if len(panels) >= 18:
            print_ok(f"Panel count meets expectation (18+)")
        else:
            print_warn(f"Expected 18+ panels, found {len(panels)}")

        refresh = dashboard.get('refresh')
        if refresh:
            print_ok(f"Auto-refresh: {refresh}")

        return True
    except Exception as e:
        print_fail(f"Dashboard check failed: {e}")
        return False

def main():
    """Run all validation checks"""
    print(f"\n{BOLD}SESSION 38 INTEGRATION VALIDATION{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    results = {
        "LLM Batch Tests": check_batch_client_tests(),
        "Behavior Engine Import": check_behavior_engine_import(),
        "Batch Methods": check_batch_methods(),
        "Database Settings": check_database_settings(),
        "Monitoring Files": check_monitoring_files(),
        "Grafana Dashboard": check_grafana_dashboard(),
    }

    # Summary
    print_section("VALIDATION SUMMARY")

    passed = sum(results.values())
    total = len(results)

    for check, result in results.items():
        if result:
            print_ok(f"{check}: PASS")
        else:
            print_fail(f"{check}: FAIL")

    print(f"\n{BOLD}RESULT: {passed}/{total} checks passed{RESET}")

    if passed == total:
        print(f"\n{GREEN}{BOLD}[SUCCESS] ALL SYSTEMS INTEGRATED AND OPERATIONAL{RESET}")
        return 0
    else:
        print(f"\n{RED}{BOLD}[ERROR] SOME CHECKS FAILED - REVIEW OUTPUT ABOVE{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
