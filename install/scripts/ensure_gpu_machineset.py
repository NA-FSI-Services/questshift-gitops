#!/usr/bin/env python3
"""Clone the first MachineSet into an L4-class GPU worker when none exist.

Workshop clusters often ship without a GPU node. This helper copies the first
MachineSet in openshift-machine-api, sets replicas=1, instanceType (default
g6.4xlarge, NVIDIA L4), and the nvidia.com/gpu NoSchedule taint.

Do not commit the rendered MachineSet — it contains cloud account details.
Generated files belong in install/.work/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from copy import deepcopy
from typing import Any

from cluster_probe import oc_json, probe

DEFAULT_INSTANCE_TYPE = "g6.4xlarge"
MACHINESET_NS = "openshift-machine-api"
MACHINESET_LABEL = "machine.openshift.io/cluster-api-machineset"
GPU_TAINT = {
    "key": "nvidia.com/gpu",
    "value": "present",
    "effect": "NoSchedule",
}
META_DROP = (
    "uid",
    "selfLink",
    "resourceVersion",
    "creationTimestamp",
    "generation",
    "managedFields",
)


def gpu_machineset_name(donor_name: str) -> str:
    if donor_name.endswith("-gpu"):
        return donor_name
    return f"{donor_name}-gpu"


def gpu_machineset_from_donor(
    donor: dict[str, Any],
    *,
    instance_type: str = DEFAULT_INSTANCE_TYPE,
    replicas: int = 1,
) -> dict[str, Any]:
    """Return a GPU MachineSet derived from a donor. No cluster I/O."""
    ms = deepcopy(donor)
    md = ms.setdefault("metadata", {})
    donor_name = str(md.get("name") or "")
    if not donor_name:
        raise ValueError("donor MachineSet has no metadata.name")
    new_name = gpu_machineset_name(donor_name)
    for key in META_DROP:
        md.pop(key, None)
    annotations = md.get("annotations") or {}
    annotations.pop("kubectl.kubernetes.io/last-applied-configuration", None)
    if annotations:
        md["annotations"] = annotations
    else:
        md.pop("annotations", None)
    md["name"] = new_name
    md["namespace"] = MACHINESET_NS
    labels = md.setdefault("labels", {})
    labels[MACHINESET_LABEL] = new_name
    ms.pop("status", None)

    spec = ms.setdefault("spec", {})
    spec["replicas"] = replicas
    selector_labels = spec.setdefault("selector", {}).setdefault("matchLabels", {})
    selector_labels[MACHINESET_LABEL] = new_name

    template = spec.setdefault("template", {})
    tmpl_labels = template.setdefault("metadata", {}).setdefault("labels", {})
    tmpl_labels[MACHINESET_LABEL] = new_name

    tspec = template.setdefault("spec", {})
    tspec["taints"] = [dict(GPU_TAINT)]

    provider = tspec.setdefault("providerSpec", {}).setdefault("value", {})
    if "instanceType" not in provider:
        raise ValueError(
            "donor MachineSet has no spec.template.spec.providerSpec.value.instanceType "
            "(AWS Machine API). Pass --no-add-gpu-nodes and add a GPU worker yourself."
        )
    provider["instanceType"] = instance_type
    return ms


def load_machinesets() -> list[dict[str, Any]]:
    data = oc_json("machinesets", "-n", MACHINESET_NS)
    if not data:
        return []
    return list(data.get("items") or [])


def oc_apply_doc(doc: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["oc", "apply", "-f", "-"],
        input=json.dumps(doc),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        check=False,
    )


def ensure_gpu_machineset(
    *,
    instance_type: str = DEFAULT_INSTANCE_TYPE,
    apply: bool = True,
    already_has_gpu: bool | None = None,
) -> dict[str, Any]:
    if already_has_gpu is None:
        report = probe()
        pci = bool(report.get("nvidia_pci_label"))
        allocatable = int(report.get("gpu_allocatable") or 0) >= 1
        already_has_gpu = pci or allocatable
    if already_has_gpu:
        return {"action": "skipped", "reason": "gpu-present"}

    items = load_machinesets()
    if not items:
        raise RuntimeError(
            "no MachineSets in openshift-machine-api; cannot clone a GPU worker. "
            "Re-run with --no-add-gpu-nodes if you will attach a GPU node yourself."
        )
    donor = items[0]
    gpu_ms = gpu_machineset_from_donor(donor, instance_type=instance_type)
    name = gpu_ms["metadata"]["name"]
    result: dict[str, Any] = {
        "action": "planned",
        "name": name,
        "donor": donor.get("metadata", {}).get("name"),
        "instanceType": instance_type,
    }
    if not apply:
        return result
    applied = oc_apply_doc(gpu_ms)
    if applied.returncode != 0:
        err = (applied.stderr or applied.stdout or "oc apply failed").strip()
        raise RuntimeError(f"oc apply MachineSet {name} failed: {err}")
    result["action"] = "applied"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clone a GPU MachineSet when the cluster has no NVIDIA GPU."
    )
    parser.add_argument(
        "--instance-type",
        default=os.environ.get("QUESTSHIFT_GPU_INSTANCE_TYPE", DEFAULT_INSTANCE_TYPE),
        help=f"AWS instance type (default {DEFAULT_INSTANCE_TYPE}, NVIDIA L4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the MachineSet without applying it",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary = ensure_gpu_machineset(instance_type=args.instance_type, apply=not args.dry_run)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    json.dump(summary, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
