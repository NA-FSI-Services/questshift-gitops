#!/usr/bin/env python3
"""Exit 0 when the named operator CSV is Succeeded."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cluster_probe import probe  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: wait_operator.py OPERATOR_ID", file=sys.stderr)
        return 2
    wanted = sys.argv[1]
    data = probe()
    for op in data.get("operators") or []:
        if op.get("id") == wanted and op.get("ready"):
            print(f"{wanted} ready csv={op.get('csv')}")
            return 0
    print(f"{wanted} not ready", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
