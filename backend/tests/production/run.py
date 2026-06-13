#!/usr/bin/env python3
"""
Production Readiness Test Runner
Usage: python backend/tests/production/run.py [options]

Options:
    --url URL       Backend URL (default: http://localhost:8000)
    --no-color      Disable colored output
    --section N     Run only section N (e.g. --section 13)
    --fast          Skip slow tests (admin rate limit)
    -v, --verbose   Verbose pytest output

Env vars:
    USER_TOKEN   JWT from browser localStorage 'tradementor_auth_token'
    ADMIN_TOKEN  JWT from browser localStorage 'tm_admin_token'
    BACKEND_URL  Override backend URL

Example:
    $env:USER_TOKEN  = "eyJ..."
    $env:ADMIN_TOKEN = "eyJ..."
    python backend/tests/production/run.py
"""

import sys
import os
import subprocess
import argparse
import httpx
from datetime import datetime


# ── ANSI colours ───────────────────────────────────────────────────────────────

def _supports_color() -> bool:
    return sys.stdout.isatty() and os.name != "nt" or os.environ.get("FORCE_COLOR") == "1"


USE_COLOR = True  # Set to False via --no-color


def c(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


GREEN  = lambda t: c(t, "32")
RED    = lambda t: c(t, "31")
YELLOW = lambda t: c(t, "33")
CYAN   = lambda t: c(t, "36")
BOLD   = lambda t: c(t, "1")
DIM    = lambda t: c(t, "2")


# ── Checklist mapping ──────────────────────────────────────────────────────────

CHECKLIST_MAP = {
    # section → [(checklist_id, description, automated?)]
    1: [
        ("1.1", "Health endpoint returns 200 + status=ok", True),
        ("1.2", "Database connection healthy",             True),
        ("1.3", "Redis connection healthy",                True),
        ("1.4", "Startup logs clean (no ERROR/CRITICAL)",  False),
        ("1.5", "ENCRYPTION_KEY valid on startup",          True),
    ],
    2: [
        ("2.1", "Connect button navigates to Zerodha",            False),
        ("2.2", "oauth_nonce cookie set on /connect",              True),
        ("2.3", "OAuth callback success → /settings?connected",   False),
        ("2.4", "Redirect to Zerodha (not JSON), no JWT in URL",  True),
        ("2.5", "Auth code consumed once (replay rejected)",      False),
        ("2.6", "Callback without nonce cookie rejected",          True),
        ("2.7", "Cancelled OAuth → error redirect",                True),
        ("2.8", "Reconnect deduplicates broker account",          False),
        ("2.9", "Disconnect works",                                False),
        ("2.10","Session expired banner at 6 AM IST",             False),
    ],
    3: [
        ("3.1",  "Dashboard loads without blank panels",          False),
        ("3.2",  "Hero metrics match Zerodha Console",            False),
        ("3.3",  "Positions table shows open positions",          False),
        ("3.4",  "Live prices update via WebSocket",              False),
        ("3.5",  "VIX displayed in hero section",                 False),
        ("3.6",  "Morning Intent card visible 7–10 AM IST",      False),
        ("3.7",  "Morning Intent saves to backend",               False),
        ("3.8",  "EOD card visible after 3:30 PM IST",           False),
        ("3.9",  "EOD card hidden outside hours",                 False),
        ("3.10", "SetupNudgeCard for fresh account",              False),
        ("3.11", "SetupNudgeCard gone after setup",               False),
        ("3.12", "AI Coach FAB opens coach panel",                False),
        ("3.13", "Guest mode loads demo data",                    False),
        ("3.14", "Guest → Connect starts OAuth",                  False),
    ],
    4: [
        ("4.1", "Alerts page loads (GET /api/risk/alerts → 200)",  True),
        ("4.2", "Empty state returns list, not error",              True),
        ("4.3", "Alert severity colours (UI)",                     False),
        ("4.4", "Acknowledge endpoint reachable",                   True),
        ("4.5", "WebSocket real-time alerts (UI)",                 False),
        ("4.6", "Alert deduplication (requires live trades)",      False),
        ("4.7", "Alert payload has required fields",                True),
    ],
    5: [
        ("5.1",  "Summary tab loads (UI)",                        False),
        ("5.2",  "Patterns tab loads (UI)",                       False),
        ("5.3",  "Trades tab loads (UI)",                         False),
        ("5.4",  "BTST tab loads (UI)",                           False),
        ("5.5",  "% Return tab loads (UI)",                       False),
        ("5.6",  "Edge Map tab — no NaN in API response",          True),
        ("5.7",  "Expiry tab — /api/analytics/expiry-pattern exists", True),
        ("5.8",  "Journal tab loads (UI)",                        False),
        ("5.9",  "Date filter respected (UI)",                    False),
        ("5.10", "Timestamps in IST (UI)",                        False),
    ],
    6: [
        ("6.1", "My Patterns page loads (UI + risk state API)",   True),
        ("6.2", "Risk state returns safe/caution/danger",          True),
        ("6.3", "Risk state has numeric score",                    True),
        ("6.4", "Patterns list populated when alerts exist (UI)", False),
    ],
    8: [
        ("8.1", "Coach endpoint reachable",                        True),
        ("8.2", "Sends AI response (manual verification)",        False),
        ("8.3", "Response streams progressively (UI)",            False),
        ("8.4", "SEBI guard rejects buy/sell advice",              True),
        ("8.5", "SEBI guard rejects price predictions",            True),
        ("8.6", "SEBI guard rejects portfolio management ask",     True),
        ("8.7", "Context uses YOUR alert data (manual)",          False),
        ("8.8", "No crash on 10+ messages",                       False),
        ("8.9", "History capped at 6 turns (manual)",             False),
    ],
    12: [
        ("12.1",  "Admin login endpoint exists",                    True),
        ("12.2",  "Wrong password → 401",                          True),
        ("12.3",  "Admin login rate limited after failures",        True),
        ("12.4",  "Dev bypass behaviour (manual)",                  False),
        ("12.5",  "TOTP enforced in prod (manual)",                 False),
        ("12.6",  "JWT expires after 8h (manual)",                  False),
        ("12.7",  "Admin overview loads",                           True),
        ("12.8",  "Overview handles null data gracefully",          True),
        ("12.9",  "Funnel stages ordered (UI)",                    False),
        ("12.10", "User list loads (UI)",                          False),
        ("12.11", "User detail loads (UI)",                        False),
        ("12.12", "Lifecycle stage logic (UI)",                    False),
        ("12.13", "Admin insights loads",                           True),
        ("12.14", "Engagement rate calculation (UI)",               False),
        ("12.15", "System health loads",                            True),
        ("12.16", "Queue depth bars (UI)",                         False),
        ("12.17", "Manual task trigger (UI)",                      False),
        ("12.18", "Broadcast loads (UI)",                          False),
        ("12.19", "Segment counts non-negative",                    True),
        ("12.20", "Template picker (UI)",                          False),
        ("12.21", "Character limit (UI)",                          False),
        ("12.22", "Send broadcast (UI/manual)",                    False),
    ],
    13: [
        ("13.1",  "GET /api/trades/ without auth → 401",           True),
        ("13.2",  "Admin endpoints without auth → blocked",         True),
        ("13.3",  "Cross-user data isolation",                      True),
        ("13.4",  "Connect is redirect, JWT not in URL",            True),
        ("13.5",  "OAuth nonce unique per session",                  True),
        ("13.6",  "Forged callback rejected (CSRF test)",           True),
        ("13.7",  "Admin IP allowlist (manual — needs two IPs)",   False),
        ("13.8",  "SQL injection in query params",                   True),
        ("13.9",  "XSS in name fields (browser manual)",           False),
        ("13.10", "Security headers present",                        True),
        ("13.11", "CORS rejects unknown origins",                    True),
        ("13.12", "API responses not cached",                        True),
        ("13.13", "Rate limit on auth (brute force test)",           True),
        ("13.14", "Access tokens encrypted in DB (manual)",         False),
        ("13.15", "Admin dev bypass ignored in prod",                True),
    ],
    14: [
        ("14.1",  "P&L matches Zerodha Console (manual)",          False),
        ("14.2",  "Short direction correct (manual)",               False),
        ("14.3",  "CNC trades filtered from API",                   True),
        ("14.4",  "Only MIS/NRML/MTF in trades list",              True),
        ("14.5",  "IST timestamps in analytics (UI)",              False),
        ("14.6",  "Daily loss alert fires (manual)",                False),
        ("14.7",  "Trade count alert fires (manual)",               False),
        ("14.8",  "Insight hours in IST (UI)",                     False),
        ("14.9",  "Insights only on ≥5-trade samples",             True),
        ("14.10", "Profile has needs_onboarding field",             True),
        ("14.11", "Onboarding skip endpoint exists",                 True),
        ("14.12", "Reconnect dedup (manual — need real OAuth)",     False),
    ],
    16: [
        ("16.1", "Zero trades → empty states not errors",           True),
        ("16.2", "100% loss rate → correct display (manual)",      False),
        ("16.3", "Backend down → graceful errors (manual)",        False),
        ("16.4", "Redis down → partial degradation (manual)",      False),
        ("16.5", "Long symbol name truncated (UI)",                False),
        ("16.6", "Large P&L is finite number in API",              True),
        ("16.7", "Multiple accounts isolated (manual)",             False),
        ("16.8", "Maintenance mode → 503 + /health still 200",     True),
        ("16.9", "Expired nonce rejected (manual — wait 6 min)",   False),
    ],
}

MANUAL_SECTIONS = {3, 5, 7, 9, 10, 11, 15, 17}


# ── Pre-flight checks ──────────────────────────────────────────────────────────

def preflight(base_url: str) -> bool:
    print(f"\n{BOLD('─── Pre-flight checks ───────────────────────────────────')}")

    # Check backend
    try:
        r = httpx.get(f"{base_url}/health", timeout=5)
        if r.status_code == 200:
            print(f"  {GREEN('✓')} Backend reachable at {base_url}")
        else:
            print(f"  {RED('✗')} Backend returned {r.status_code} at {base_url}")
            return False
    except Exception as e:
        print(f"  {RED('✗')} Backend NOT reachable at {base_url}: {e}")
        print(f"    {DIM('Start it: cd backend && uvicorn app.main:app --reload --port 8000')}")
        return False

    # Check tokens
    user_token  = os.environ.get("USER_TOKEN", "").strip()
    admin_token = os.environ.get("ADMIN_TOKEN", "").strip()

    if user_token:
        print(f"  {GREEN('✓')} USER_TOKEN set — authenticated tests will run")
    else:
        print(f"  {YELLOW('!')} USER_TOKEN not set — tests requiring auth will be skipped")
        print(f"    {DIM('Get it: DevTools → Application → Local Storage → tradementor_auth_token')}")

    if admin_token:
        print(f"  {GREEN('✓')} ADMIN_TOKEN set — admin tests will run")
    else:
        print(f"  {YELLOW('!')} ADMIN_TOKEN not set — admin panel tests will be skipped")
        print(f"    {DIM('Get it: Log into /admin → DevTools → Local Storage → tm_admin_token')}")

    return True


# ── Checklist summary ──────────────────────────────────────────────────────────

def print_checklist_summary(section_filter: int | None = None):
    print(f"\n{BOLD('─── Automated coverage by section ──────────────────────')}")

    sections = [section_filter] if section_filter else sorted(CHECKLIST_MAP.keys())

    total_items = 0
    total_automated = 0

    for sec in sections:
        items = CHECKLIST_MAP.get(sec, [])
        automated = [i for i in items if i[2]]
        manual = [i for i in items if not i[2]]
        total_items += len(items)
        total_automated += len(automated)

        print(f"\n  {BOLD(f'Section {sec}')}  ({len(automated)}/{len(items)} automated)")
        for cid, desc, is_auto in items:
            if is_auto:
                print(f"    {GREEN('●')} {cid:<6} {desc}")
            else:
                print(f"    {DIM('○')} {cid:<6} {DIM(desc)}  {DIM('[manual]')}")

    for sec in sorted(MANUAL_SECTIONS):
        if section_filter and sec != section_filter:
            continue
        print(f"\n  {BOLD(f'Section {sec}')}  {DIM('(all manual — UI/timing/real-broker)')}")

    print(f"\n  {BOLD('Total:')} {total_automated}/{total_items} tests automated "
          f"({int(total_automated/total_items*100)}%)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global USE_COLOR

    parser = argparse.ArgumentParser(description="Production readiness test runner")
    parser.add_argument("--url",      default=None,  help="Backend URL")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--section",  type=int, default=None, help="Run only this section")
    parser.add_argument("--fast",     action="store_true", help="Skip rate-limit tests")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--list",     action="store_true", help="List coverage map and exit")
    args = parser.parse_args()

    if args.no_color:
        USE_COLOR = False

    base_url = args.url or os.environ.get("BACKEND_URL", "http://localhost:8000")
    os.environ["BACKEND_URL"] = base_url

    print(f"\n{BOLD(CYAN('TradeMentor AI — Production Readiness Tests'))}")
    print(f"{DIM(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")

    if args.list:
        print_checklist_summary(args.section)
        return

    if not preflight(base_url):
        sys.exit(1)

    print_checklist_summary(args.section)

    # Build pytest command
    test_dir = os.path.join(os.path.dirname(__file__))

    cmd = [sys.executable, "-m", "pytest", test_dir]

    if args.section:
        marker_map = {
            1: "section1", 2: "section2", 4: "section4",
            6: "section4",  # section4 file covers 4+6
            8: "section8", 12: "section12", 13: "section13",
            14: "section14", 16: "section16",
        }
        mark = marker_map.get(args.section)
        if mark:
            cmd += ["-m", mark]
        else:
            print(f"{YELLOW('!')} No automated tests for section {args.section}")
            return

    cmd += ["--tb=short", "-q"]
    if args.verbose:
        cmd += ["-v"]
    if args.fast:
        cmd += ["-m", "not slow"]

    # Add root src for imports
    cmd += ["--rootdir", os.path.join(os.path.dirname(__file__), "..", "..", "..")]

    print(f"\n{BOLD('─── Running tests ───────────────────────────────────────')}")
    print(f"  {DIM(' '.join(cmd))}\n")

    result = subprocess.run(cmd, cwd=os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    print(f"\n{BOLD('─── Manual tests remaining ──────────────────────────────')}")
    print(f"  Sections requiring manual verification:")
    print(f"  {DIM('2.1/2.3/2.5/2.8/2.9/2.10')} — Full Zerodha OAuth (needs real login)")
    print(f"  {DIM('3.x')}  — Dashboard UI (open browser, check each card)")
    print(f"  {DIM('5.x')}  — Analytics tabs (open each tab, verify data renders)")
    print(f"  {DIM('9.x')}  — Settings UI")
    print(f"  {DIM('10.x')} — Onboarding wizard (step navigation, skip, repeat check)")
    print(f"  {DIM('13.9')} — XSS test (paste <script>alert(1)</script> in name field)")
    print(f"  {DIM('13.14')}— DB column inspection (check access_token is encrypted ciphertext)")
    print(f"  {DIM('15.x')} — Mobile/responsive (open DevTools → mobile view)")
    print(f"  {DIM('17.x')} — Celery tasks (wait for 8:30 AM / 3:35 PM IST)")
    print(f"  {DIM('See docs/testing/PRODUCTION_READINESS_CHECKLIST.md for all manual steps')}")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
