#!/usr/bin/env python3
"""Exit 0 when the Argo CD Application is Synced and Healthy."""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: wait_application.py NAMESPACE NAME", file=sys.stderr)
        return 2
    namespace, name = sys.argv[1], sys.argv[2]
    result = subprocess.run(
        ["oc", "get", "application.argoproj.io", name, "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "application not found", file=sys.stderr)
        return 1
    app = json.loads(result.stdout)
    status = app.get("status") or {}
    health = ((status.get("health") or {}).get("status") or "").lower()
    sync = ((status.get("sync") or {}).get("status") or "").lower()
    print(f"sync={sync} health={health}")
    return 0 if health == "healthy" and sync == "synced" else 1


if __name__ == "__main__":
    raise SystemExit(main())
