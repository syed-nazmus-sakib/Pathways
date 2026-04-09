"""
PATHWAYS v3 — Injection and Verification Script
=================================================
Step 1: Inject SQL into the running Magento Docker container
Step 2: Verify every task URL is accessible and has correct data

Usage:
    # Inject + verify all:
    python3 inject_and_verify_v3.py --inject --verify

    # Verify only (after manual injection):
    python3 inject_and_verify_v3.py --verify

    # Single task debug:
    python3 inject_and_verify_v3.py --verify --task PW3_RESHIP_001
"""

import json
import time
import subprocess
import sys
import os
import argparse
import requests
from typing import Dict, List, Tuple, Optional

# =============================================================================
# CONFIG
# =============================================================================
CONTAINER_NAME   = "shopping_admin"
DB_USER          = "magentouser"
DB_PASS          = "MyPassword"
DB_NAME          = "magentodb"
ADMIN_BASE       = "http://localhost:7780"
ADMIN_USER       = "admin"
ADMIN_PASS       = "admin1234"
SQL_FILE         = "pathways_v3_shopping_data.sql"
TASKS_FILE       = "pathways_v3_shopping_tasks.json"

REST_BASE        = f"{ADMIN_BASE}/rest/V1"
VERIFY_REPORT_FILE = "pathways_v3_verification_report.json"


# =============================================================================
# INJECTION
# =============================================================================
def inject_sql(sql_file: str, sudo_password: str = None) -> bool:
    """
    Copy SQL file into container and run it via mysql.
    Requires either:
      - The current user to be in the docker group, OR
      - sudo access (will prompt for password)
    """
    abs_path = os.path.abspath(sql_file)
    if not os.path.exists(abs_path):
        print(f"[ERROR] SQL file not found: {abs_path}")
        return False

    print(f"[INJECT] Copying {sql_file} into container...")
    cp_cmd = ["docker", "cp", abs_path, f"{CONTAINER_NAME}:/tmp/pathways_v3_inject.sql"]

    if sudo_password:
        cp_cmd = ["sudo", "-S"] + cp_cmd
        cp_result = subprocess.run(cp_cmd, input=sudo_password + "\n",
                                    capture_output=True, text=True)
    else:
        cp_result = subprocess.run(cp_cmd, capture_output=True, text=True)

    if cp_result.returncode != 0:
        print(f"[ERROR] docker cp failed: {cp_result.stderr}")
        print("  → Make sure you are in the 'docker' group or have sudo access")
        return False

    print("[INJECT] Running SQL injection...")
    exec_cmd = ["docker", "exec", CONTAINER_NAME, "mysql",
                f"-u{DB_USER}", f"-p{DB_PASS}", DB_NAME,
                "-e", "source /tmp/pathways_v3_inject.sql"]

    if sudo_password:
        exec_cmd = ["sudo", "-S"] + exec_cmd
        exec_result = subprocess.run(exec_cmd, input=sudo_password + "\n",
                                      capture_output=True, text=True, timeout=120)
    else:
        exec_result = subprocess.run(exec_cmd, capture_output=True, text=True, timeout=120)

    if exec_result.returncode != 0:
        print(f"[ERROR] mysql injection failed: {exec_result.stderr[:500]}")
        return False

    print("[INJECT] Flushing Magento cache...")
    flush_cmd = ["docker", "exec", CONTAINER_NAME,
                 "php", "/var/www/magento2/bin/magento", "cache:flush"]
    if sudo_password:
        flush_cmd = ["sudo", "-S"] + flush_cmd
        subprocess.run(flush_cmd, input=sudo_password + "\n",
                       capture_output=True, text=True, timeout=60)
    else:
        subprocess.run(flush_cmd, capture_output=True, text=True, timeout=60)

    print("[INJECT] ✓ Injection complete")
    return True


def inject_sql_heredoc(sql_file: str) -> None:
    """
    Print the exact commands the user needs to run manually if sudo is unavailable.
    """
    abs_path = os.path.abspath(sql_file)
    print("\n" + "="*70)
    print("MANUAL INJECTION COMMANDS")
    print("="*70)
    print("Run these commands in your terminal:\n")
    print(f"  sudo docker cp {abs_path} {CONTAINER_NAME}:/tmp/pathways_v3_inject.sql")
    print(f"  sudo docker exec {CONTAINER_NAME} mysql -u{DB_USER} -p{DB_PASS} {DB_NAME} < /tmp/pathways_v3_inject.sql")
    print(f"  sudo docker exec {CONTAINER_NAME} php /var/www/magento2/bin/magento cache:flush")
    print("="*70 + "\n")


# =============================================================================
# REST API HELPERS
# =============================================================================
_token: Optional[str] = None

def get_token() -> str:
    global _token
    if _token:
        return _token
    resp = requests.post(
        f"{REST_BASE}/integration/admin/token/",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15
    )
    _token = resp.json().strip('"') if resp.status_code == 200 else None
    return _token

def api_get(path: str) -> Optional[dict]:
    token = get_token()
    if not token:
        return None
    try:
        resp = requests.get(f"{REST_BASE}{path}",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[API ERROR] {e}")
    return None


# =============================================================================
# VERIFICATION
# =============================================================================

def verify_customer(customer_id: int) -> Tuple[bool, str]:
    """Check customer exists via REST API."""
    data = api_get(f"/customers/{customer_id}")
    if data and "id" in data:
        return True, f"{data['firstname']} {data['lastname']} ({data['email']})"
    return False, "NOT FOUND"


def verify_order(order_id: int, expected_customer_id: int) -> Tuple[bool, str]:
    """Check order exists and belongs to correct customer."""
    data = api_get(f"/orders/{order_id}")
    if not data:
        return False, "NOT FOUND"

    found_customer = data.get("customer_id") or data.get("base_customer_id")
    if str(found_customer) != str(expected_customer_id):
        return False, f"Customer mismatch: found {found_customer}, expected {expected_customer_id}"

    return True, (f"inc={data.get('increment_id')} "
                  f"total={data.get('grand_total')} "
                  f"status={data.get('status')}")


def verify_order_has_shipping_diversity(order_ids: List[int]) -> Tuple[bool, str]:
    """For reshipping_fraud: verify that shipping addresses span multiple states."""
    states = set()
    for oid in order_ids:
        data = api_get(f"/orders/{oid}")
        if not data:
            continue
        for ext in data.get("extension_attributes", {}).get("shipping_assignments", []):
            addr = ext.get("shipping", {}).get("address", {})
            if addr.get("region_code"):
                states.add(addr["region_code"])

    if len(states) >= 4:
        return True, f"Shipping spans {len(states)} states: {sorted(states)}"
    return False, f"Only {len(states)} distinct shipping states found: {sorted(states)}"


def verify_url_accessible(url: str) -> Tuple[bool, int]:
    """Check a Magento admin URL returns 200 (after cookie-based login)."""
    try:
        # Use a session to maintain the login cookie
        session = _get_admin_session()
        resp = session.get(url, timeout=20, allow_redirects=True)
        return resp.status_code == 200, resp.status_code
    except Exception as e:
        return False, 0


_admin_session: Optional[requests.Session] = None

def _get_admin_session() -> requests.Session:
    global _admin_session
    if _admin_session:
        return _admin_session

    session = requests.Session()
    # Get login page for form_key
    login_page = session.get(f"{ADMIN_BASE}/admin/", timeout=15)
    import re
    form_key_match = re.search(r'name="form_key"\s+value="([^"]+)"', login_page.text)
    form_key = form_key_match.group(1) if form_key_match else ""

    # Login
    session.post(
        f"{ADMIN_BASE}/admin/auth/login/",
        data={
            "login[username]": ADMIN_USER,
            "login[password]": ADMIN_PASS,
            "form_key": form_key,
        },
        timeout=20,
        allow_redirects=True,
    )
    _admin_session = session
    return session


def verify_task(task: Dict, verbose: bool = False) -> Dict:
    """
    Full verification for a single task.
    Returns a verification report dict.
    """
    task_id = task["task_id"]
    category = task["category"]
    customer_id = task["customer"]["id"]
    target_order_id = task["target_order"]["id"]
    prior_order_ids = task.get("prior_order_ids", [])
    target_url = task["target_order"]["url"]

    report = {
        "task_id": task_id,
        "category": category,
        "customer_id": customer_id,
        "target_order_id": target_order_id,
        "checks": {},
        "passed": False,
        "issues": [],
    }

    # 1. Customer exists
    cust_ok, cust_msg = verify_customer(customer_id)
    report["checks"]["customer_exists"] = {"pass": cust_ok, "detail": cust_msg}
    if not cust_ok:
        report["issues"].append(f"Customer {customer_id} not found")

    # 2. Target order exists
    order_ok, order_msg = verify_order(target_order_id, customer_id)
    report["checks"]["target_order_exists"] = {"pass": order_ok, "detail": order_msg}
    if not order_ok:
        report["issues"].append(f"Target order {target_order_id} not found or wrong customer")

    # 3. Target URL is accessible
    url_ok, status_code = verify_url_accessible(target_url)
    report["checks"]["target_url_accessible"] = {
        "pass": url_ok, "url": target_url, "status": status_code
    }
    if not url_ok:
        report["issues"].append(f"Target URL {target_url} returned {status_code}")

    # 4. Prior orders all exist
    prior_ok_count = 0
    for oid in prior_order_ids:
        ok, _ = verify_order(oid, customer_id)
        if ok:
            prior_ok_count += 1

    prior_all_ok = (prior_ok_count == len(prior_order_ids))
    report["checks"]["prior_orders_exist"] = {
        "pass": prior_all_ok,
        "detail": f"{prior_ok_count}/{len(prior_order_ids)} prior orders found"
    }
    if not prior_all_ok:
        report["issues"].append(f"Only {prior_ok_count}/{len(prior_order_ids)} prior orders found")

    # 5. Category-specific checks
    if category == "reshipping_fraud":
        diversity_ok, diversity_msg = verify_order_has_shipping_diversity(prior_order_ids)
        report["checks"]["shipping_diversity"] = {"pass": diversity_ok, "detail": diversity_msg}
        if not diversity_ok:
            report["issues"].append(f"Reshipping fraud: insufficient address diversity")

    # 6. No analytical comments on target order
    order_data = api_get(f"/orders/{target_order_id}")
    has_analytical_comment = False
    if order_data:
        status_histories = order_data.get("status_histories", [])
        for hist in status_histories:
            comment = hist.get("comment", "")
            for keyword in ["FRAUD ALERT", "DO NOT PROCESS", "ESCALATE TO LOSS",
                            "APPROVE - recommend", "CUSTOMER ANALYSIS", "Loss Prevention"]:
                if keyword.lower() in comment.lower():
                    has_analytical_comment = True
                    report["issues"].append(f"Analytical comment found: '{comment[:80]}...'")
                    break
    report["checks"]["no_analytical_comments"] = {
        "pass": not has_analytical_comment,
        "detail": "No pre-written analysis found in order history"
    }

    # Overall pass: all critical checks pass
    critical = ["customer_exists", "target_order_exists", "target_url_accessible",
                "prior_orders_exist", "no_analytical_comments"]
    report["passed"] = all(report["checks"].get(c, {}).get("pass", False)
                           for c in critical)

    if verbose:
        status = "✓ PASS" if report["passed"] else "✗ FAIL"
        print(f"  [{status}] {task_id} ({category}) — {len(report['issues'])} issue(s)")
        for issue in report["issues"]:
            print(f"         └─ {issue}")

    return report


def run_verification(tasks_file: str, filter_task_id: str = None,
                     max_tasks: int = None) -> List[Dict]:
    """Run verification across all tasks. Returns list of reports."""
    with open(tasks_file) as f:
        data = json.load(f)

    tasks = data["tasks"]
    if filter_task_id:
        tasks = [t for t in tasks if t["task_id"] == filter_task_id]
    if max_tasks:
        tasks = tasks[:max_tasks]

    print(f"\n{'='*60}")
    print(f"PATHWAYS v3 Verification — {len(tasks)} tasks")
    print(f"{'='*60}\n")

    # Verify token works
    token = get_token()
    if not token:
        print("[ERROR] Cannot get Magento API token. Is the container running?")
        return []

    reports = []
    passed = 0
    failed = 0

    for i, task in enumerate(tasks, 1):
        print(f"[{i:3d}/{len(tasks)}]", end=" ")
        report = verify_task(task, verbose=True)
        reports.append(report)
        if report["passed"]:
            passed += 1
        else:
            failed += 1

        # Small delay to avoid overwhelming the server
        if i % 10 == 0:
            time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{len(tasks)} passed ({failed} failed)")

    # Category breakdown
    from collections import defaultdict
    cat_results = defaultdict(lambda: {"pass": 0, "fail": 0})
    for r in reports:
        if r["passed"]:
            cat_results[r["category"]]["pass"] += 1
        else:
            cat_results[r["category"]]["fail"] += 1

    print("\nBy category:")
    for cat, res in sorted(cat_results.items()):
        total = res["pass"] + res["fail"]
        print(f"  {cat:<25} {res['pass']:3d}/{total} passed")

    # Save report
    with open(VERIFY_REPORT_FILE, "w") as f:
        json.dump({
            "total": len(tasks),
            "passed": passed,
            "failed": failed,
            "tasks": reports
        }, f, indent=2)
    print(f"\nDetailed report saved to: {VERIFY_REPORT_FILE}")
    print(f"{'='*60}\n")

    return reports


def print_failed_details(reports: List[Dict]):
    """Print details about failed tasks for debugging."""
    failed = [r for r in reports if not r["passed"]]
    if not failed:
        print("All tasks passed!")
        return

    print(f"\n{'='*60}")
    print(f"FAILED TASKS ({len(failed)}):")
    print(f"{'='*60}")
    for r in failed:
        print(f"\n  Task: {r['task_id']}")
        print(f"  Category: {r['category']}")
        print(f"  Issues:")
        for issue in r["issues"]:
            print(f"    → {issue}")


# =============================================================================
# MAIN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="PATHWAYS v3 Injection and Verification"
    )
    parser.add_argument("--inject", action="store_true",
                        help="Inject SQL into Docker container")
    parser.add_argument("--verify", action="store_true",
                        help="Verify all task URLs and data")
    parser.add_argument("--task", type=str, default=None,
                        help="Verify a single task by ID")
    parser.add_argument("--show-manual", action="store_true",
                        help="Print manual injection commands")
    parser.add_argument("--sudo-pass", type=str, default=None,
                        help="Sudo password for docker exec (optional)")
    parser.add_argument("--sql", default=SQL_FILE,
                        help=f"SQL file to inject (default: {SQL_FILE})")
    parser.add_argument("--tasks", default=TASKS_FILE,
                        help=f"Tasks JSON file (default: {TASKS_FILE})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit verification to first N tasks")
    parser.add_argument("--failed-only", action="store_true",
                        help="After verify, print detailed failed task info")
    args = parser.parse_args()

    if not args.inject and not args.verify and not args.show_manual:
        parser.print_help()
        sys.exit(1)

    if args.show_manual:
        inject_sql_heredoc(args.sql)

    if args.inject:
        success = inject_sql(args.sql, sudo_password=args.sudo_pass)
        if not success:
            print("\n[INFO] Automatic injection failed. Use --show-manual for instructions.")
            inject_sql_heredoc(args.sql)

    if args.verify:
        reports = run_verification(
            args.tasks,
            filter_task_id=args.task,
            max_tasks=args.limit
        )
        if args.failed_only:
            print_failed_details(reports)


if __name__ == "__main__":
    main()
