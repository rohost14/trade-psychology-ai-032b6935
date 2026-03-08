#!/usr/bin/env python
"""
Celery Worker Startup Script

Usage:
    # Start worker for all queues:
    python scripts/run_celery.py worker

    # Start worker for specific queue:
    python scripts/run_celery.py worker --queue trades

    # Start beat scheduler (for periodic tasks):
    python scripts/run_celery.py beat

    # Start both worker and beat:
    python scripts/run_celery.py all
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.celery_app import celery_app


def start_worker(queues=None, concurrency=4):
    """Start Celery worker."""
    argv = [
        "worker",
        f"--concurrency={concurrency}",
        "--loglevel=info",
        "-E",  # Send events for monitoring
    ]

    if queues:
        argv.append(f"--queues={queues}")
    else:
        # Listen to all queues
        argv.append("--queues=trades,alerts,reports,celery")

    # Windows doesn't support prefork
    if sys.platform == "win32":
        argv.append("--pool=solo")

    celery_app.worker_main(argv)


def start_beat():
    """Start Celery beat scheduler."""
    argv = [
        "beat",
        "--loglevel=info",
    ]
    celery_app.start(argv)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "worker":
        queues = None
        concurrency = 4

        # Parse arguments
        for i, arg in enumerate(sys.argv[2:]):
            if arg.startswith("--queue="):
                queues = arg.split("=")[1]
            elif arg.startswith("--concurrency="):
                concurrency = int(arg.split("=")[1])

        print(f"Starting Celery worker (queues={queues or 'all'}, concurrency={concurrency})")
        start_worker(queues, concurrency)

    elif command == "beat":
        print("Starting Celery beat scheduler")
        start_beat()

    elif command == "all":
        print("Starting both worker and beat...")
        print("Note: In production, run these separately")

        # Start worker with beat
        argv = [
            "worker",
            "--beat",
            "--concurrency=4",
            "--loglevel=info",
            "--queues=trades,alerts,reports,celery",
        ]

        if sys.platform == "win32":
            argv.append("--pool=solo")

        celery_app.worker_main(argv)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
