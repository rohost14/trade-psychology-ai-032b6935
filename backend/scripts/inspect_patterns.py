import inspect
import sys
import os

# Ensure the backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import behavioral_analysis_service

def get_all_patterns():
    patterns = []
    for name, obj in inspect.getmembers(behavioral_analysis_service):
        if inspect.isclass(obj) and issubclass(obj, behavioral_analysis_service.BehavioralPattern) and obj != behavioral_analysis_service.BehavioralPattern:
            patterns.append(obj)
    
    print(f"Found {len(patterns)} Behavioral Patterns:")
    for p in patterns:
        instance = p()
        print(f"- {p.__name__} (Name: '{instance.name}', Category: '{instance.category}', Severity: '{instance.severity}')")

if __name__ == "__main__":
    get_all_patterns()
