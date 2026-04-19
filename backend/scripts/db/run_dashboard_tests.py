"""
Run Dashboard API tests and save full output to tests/dashboard_test_results.txt

Usage:
    cd backend
    python run_dashboard_tests.py
"""

import subprocess
import sys
import os
from datetime import datetime

output_file = os.path.join(os.path.dirname(__file__), "tests", "dashboard_test_results.txt")

cmd = [
    sys.executable, "-m", "pytest",
    "tests/test_dashboard_api.py",
    "-v",
    "-s",
    "--tb=long",
    "--no-header",
    "-p", "no:warnings",
]

print(f"Running: {' '.join(cmd)}")
print(f"Output:  {output_file}\n")

result = subprocess.run(cmd, capture_output=True, text=True)
output = result.stdout + result.stderr

# Write to file
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("=" * 70 + "\n\n")
    f.write(output)

# Also print to terminal
print(output)

# Summary line
lines = output.splitlines()
summary = next((l for l in reversed(lines) if "passed" in l or "failed" in l or "error" in l), "")
print(f"\n{'='*70}")
print(f"SUMMARY: {summary}")
print(f"Full results: {output_file}")

sys.exit(result.returncode)
