#!/usr/bin/env python3
"""Exit 0 when the Tekton PipelineRun Succeeded."""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: wait_pipelinerun.py NAMESPACE NAME", file=sys.stderr)
        return 2
    namespace, name = sys.argv[1], sys.argv[2]
    result = subprocess.run(
        ["oc", "get", "pipelinerun.tekton.dev", name, "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "pipelinerun not found", file=sys.stderr)
        return 1
    run = json.loads(result.stdout)
    conditions = ((run.get("status") or {}).get("conditions")) or []
    succeeded = next((c for c in conditions if c.get("type") == "Succeeded"), {})
    status = (succeeded.get("status") or "").lower()
    reason = succeeded.get("reason") or ""
    print(f"succeeded={status} reason={reason}")
    if status == "false":
        return 1
    return 0 if status == "true" else 1


if __name__ == "__main__":
    raise SystemExit(main())
