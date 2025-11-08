"""
Comprehensive Session 43 Testing Suite
Tests all new features: Setup Wizard, Health Dashboard, User Management
"""
import os
import sys
import json
import time
import requests
from datetime import datetime

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
FRONTEND_BASE = os.getenv("FRONTEND_BASE", "http://localhost:5173")
API_KEY = os.getenv("API_KEY", "change-me")

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")

def print_test(name, passed, details=""):
    """Print test result"""
    status = f"{Colors.GREEN}[PASS]" if passed else f"{Colors.RED}[FAIL]"
    print(f"{status}{Colors.RESET} {name}")
    if details:
        print(f"       {details}")

def test_setup_wizard_api():
    """Test Setup Wizard API endpoints"""
    print_section("Setup Wizard API Tests")

    results = []

    # Test 1: Setup Status
    try:
        response = requests.get(f"{API_BASE}/setup/status", timeout=5)
        passed = response.status_code == 200
        data = response.json() if passed else {}

        print_test(
            "GET /setup/status",
            passed,
            f"Status: {response.status_code}, Has admin: {data.get('has_admin_user', 'N/A')}"
        )
        results.append(("Setup Status API", passed))
    except Exception as e:
        print_test("GET /setup/status", False, f"Error: {e}")
        results.append(("Setup Status API", False))

    return results

def test_health_dashboard_api():
    """Test Health Dashboard API endpoint"""
    print_section("Health Dashboard API Tests")

    results = []
    headers = {"X-API-Key": API_KEY}

    # Test 1: Health Endpoint
    try:
        response = requests.get(f"{API_BASE}/system/health", headers=headers, timeout=5)
        passed = response.status_code == 200
        data = response.json() if passed else {}

        overall_status = data.get('overall_status', 'unknown')
        worker_status = data.get('worker', {}).get('status', 'unknown')
        db_status = data.get('database', {}).get('status', 'unknown')

        print_test(
            "GET /system/health",
            passed,
            f"Overall: {overall_status}, Worker: {worker_status}, DB: {db_status}"
        )
        results.append(("Health Dashboard API", passed))

        # Test 2: Check all components
        if passed:
            components = ['api', 'worker', 'database', 'redis', 'disk']
            for component in components:
                has_component = component in data
                comp_status = data.get(component, {}).get('status', 'missing') if has_component else 'missing'
                print_test(
                    f"  Component: {component}",
                    has_component,
                    f"Status: {comp_status}"
                )
                results.append((f"Health - {component}", has_component))

    except Exception as e:
        print_test("GET /system/health", False, f"Error: {e}")
        results.append(("Health Dashboard API", False))

    return results

def test_frontend_availability():
    """Test Frontend is serving"""
    print_section("Frontend Availability Tests")

    results = []

    # Test 1: Frontend loads
    try:
        response = requests.get(FRONTEND_BASE, timeout=5)
        passed = response.status_code == 200 and len(response.text) > 100

        print_test(
            f"GET {FRONTEND_BASE}",
            passed,
            f"Status: {response.status_code}, Size: {len(response.text)} bytes"
        )
        results.append(("Frontend Available", passed))

        # Test 2: Check for JavaScript bundle
        if passed:
            has_js = "index-" in response.text and ".js" in response.text
            print_test(
                "  JavaScript bundle present",
                has_js,
                "index-*.js found in HTML" if has_js else "No bundle found"
            )
            results.append(("Frontend JS Bundle", has_js))

    except Exception as e:
        print_test(f"GET {FRONTEND_BASE}", False, f"Error: {e}")
        results.append(("Frontend Available", False))

    return results

def test_component_integration():
    """Test that new components are integrated"""
    print_section("Component Integration Tests")

    results = []

    # Check if components exist in filesystem
    components = [
        ("SetupWizard.jsx", "components/SetupWizard.jsx"),
        ("HealthDashboard.jsx", "components/HealthDashboard.jsx"),
        ("UserManagement.jsx", "UserManagement.jsx"),  # Root folder, not components/
    ]

    for name, path in components:
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0

        print_test(
            f"File: {name}",
            exists,
            f"Size: {size:,} bytes" if exists else "Not found"
        )
        results.append((f"Component - {name}", exists))

    # Check if components are imported in App.jsx
    try:
        with open("App.jsx", "r", encoding="utf-8") as f:
            app_content = f.read()

        imports_to_check = [
            ("SetupWizard import", "import SetupWizard"),
            ("HealthDashboard import", "import HealthDashboard"),
        ]

        for name, import_str in imports_to_check:
            has_import = import_str in app_content
            print_test(
                f"  {name}",
                has_import,
                "Found in App.jsx" if has_import else "Missing in App.jsx"
            )
            results.append((name, has_import))

    except Exception as e:
        print_test("App.jsx check", False, f"Error: {e}")
        results.append(("App.jsx check", False))

    return results

def generate_test_report(all_results):
    """Generate and save test report"""
    print_section("Test Summary")

    total = len(all_results)
    passed = sum(1 for _, result in all_results if result)
    failed = total - passed
    success_rate = (passed / total * 100) if total > 0 else 0

    print(f"Total Tests: {total}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
    print(f"Success Rate: {success_rate:.1f}%\n")

    # Generate JSON report
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": success_rate
        },
        "tests": [
            {"name": name, "passed": result}
            for name, result in all_results
        ]
    }

    report_path = "test_session43_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to: {report_path}")

    # Return exit code
    return 0 if failed == 0 else 1

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}Session 43 Comprehensive Test Suite{Colors.RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    all_results = []

    # Run all test suites
    all_results.extend(test_setup_wizard_api())
    all_results.extend(test_health_dashboard_api())
    all_results.extend(test_frontend_availability())
    all_results.extend(test_component_integration())

    # Generate report
    exit_code = generate_test_report(all_results)

    if exit_code == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.RESET}\n")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}Some tests failed. Review output above.{Colors.RESET}\n")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())
