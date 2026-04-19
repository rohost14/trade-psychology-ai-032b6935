import sys
import os
import time

# Add backend dir to sys.path
sys.path.append(os.getcwd())

def test_import(module_name):
    print(f"Importing {module_name}...", end="", flush=True)
    start = time.time()
    try:
        __import__(module_name)
        print(f" Done ({time.time() - start:.3f}s)")
    except Exception as e:
        print(f"\nFAILED to import {module_name}: {e}")
        import traceback
        traceback.print_exc()

print("Starting import tests...")

# Core
test_import("app.core.config")
test_import("app.core.database")
test_import("app.core.logging_config")

# Services
test_import("app.services.rag_service")
test_import("app.services.retention_service")

# APIs (as listed in main.py)
test_import("app.api.zerodha")
test_import("app.api.trades")
test_import("app.api.positions")
test_import("app.api.webhooks")
test_import("app.api.risk")
test_import("app.api.alerts")
test_import("app.api.settings")
test_import("app.api.analytics")
test_import("app.api.behavioral")
test_import("app.api.coach")
test_import("app.api.reports")
test_import("app.api.goals")
test_import("app.api.websocket")
test_import("app.api.notifications")
test_import("app.api.journal")
test_import("app.api.profile")
test_import("app.api.cooldown")
test_import("app.api.personalization")
test_import("app.api.danger_zone")

print("All imports attempted.")
