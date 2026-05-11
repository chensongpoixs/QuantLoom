#!/usr/bin/env python3
"""等价于: python scripts/run_scanner.py --top 0（可再跟 --dry-run、--skip-events）"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SCRIPTS))

sys.argv = [sys.argv[0], "--top", "0"] + sys.argv[1:]

import run_scanner as _scanner


def main() -> None:
    dry = "--dry-run" in sys.argv
    top_n = _scanner.parse_top_n()
    skip_events = "--skip-events" in sys.argv
    _scanner.main(dry_run=dry, top_n=top_n, skip_events=skip_events)


if __name__ == "__main__":
    main()
