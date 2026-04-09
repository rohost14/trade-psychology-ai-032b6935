
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.core.config import settings
    print(f"SUCCESS: Settings loaded. SECRET_KEY is set.")
except Exception as e:
    print(f"ERROR: {e}")
