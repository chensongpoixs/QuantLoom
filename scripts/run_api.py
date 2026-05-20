#!/usr/bin/env python3
"""等价于: uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090"""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    import uvicorn

    uvicorn.run("quant_loom.api.app:app", host="0.0.0.0", port=20015)


if __name__ == "__main__":
    main()
