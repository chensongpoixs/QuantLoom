#!/usr/bin/env python3
"""等价于: celery -A quant_loom.tasks.celery_app worker -l info --pool=threads --concurrency=2"""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    sys.argv = [
        "celery",
        "-A",
        "quant_loom.tasks.celery_app",
        "worker",
        "-l",
        "info",
        "--pool=threads",
        "--concurrency=2",
    ]
    from celery.bin.celery import main as celery_main

    celery_main()


if __name__ == "__main__":
    main()
