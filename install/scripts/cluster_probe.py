#!/usr/bin/env python3
"""Read-only OpenShift probe for the QuestShift installer. Prints JSON. No secrets."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any


CHANNEL_FALLBACKS = {
    "nfd": "stable",
    "gpu-operator-certified": "v26.3",
    "openshift-gitops-operator": "latest",
    "rhods-operator": "stable",
}

REQUIRED_OPERATORS = (
    {
        "id": "nfd",
        "title": "Node Feature Discovery",
        "csv_prefixes": ("nfd.",),
        "subscription_names": ("nfd",),
    },
    {
        "id": "gpu-operator-certified",
        "title": "NVIDIA GPU Operator",
        "csv_prefixes": ("gpu-operator-certified.",),
        "subscription_names": ("gpu-operator-certified",),
    },
    {
        "id": "openshift-gitops-operator",
        "title": "Red Hat OpenShift GitOps",
        "csv_prefixes": ("openshift-gitops-operator.",),
        "subscription_names": ("openshift-gitops-operator",),
    },
    {
        "id": "rhods-operator",
        "title": "Red Hat OpenShift AI",
        "csv_prefixes": ("rhods-operator.",),
        "subscription_names": ("rhods-operator",),
    },
)

# Requests from k8s/* workloads (one party).
NEED_CPU_MILLIS = 2300  # 2 + 250m + 50m
NEED_MEMORY_MI = 16 * 1024 + 512 + 64
NEED_GPU = 1
NEED_STORAGE_GI = 51
MIN_OCP = (4, 20)
MIN_WORKERS = 1
RECOMMENDED_WORKERS = 2


def oc(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    return subprocess.run(
        ["oc", *args],
        check=check,
        text=True,
        capture_output=True,
        env=env,
    )


def oc_json(*args: str) -> Any:
    result = oc("get", *args, "-o", "json", check=False)
    if result.returncode != 0:
        return None
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def parse_cpu_millis(value: str | None) -> int:
    if not value:
        return 0
    value = str(value)
    if value.endswith("m"):
        return int(value[:-1])
    if value.endswith("n"):
        return int(int(value[:-1]) / 1_000_000)
    return int(float(value) * 1000)


def parse_memory_mi(value: str | None) -> int:
    if not value:
        return 0
    raw = str(value)
    multipliers = {
        "Ki": 1 / 1024,
        "Mi": 1,
        "Gi": 1024,
        "Ti": 1024 * 1024,
        "K": 1 / 1024,
        "M": 1,
        "G": 1024,
        "T": 1024 * 1024,
        "k": 1 / 1024,
        "m": 1 / (1024 * 1024),
    }
    for suffix, factor in multipliers.items():
        if raw.endswith(suffix):
            return int(float(raw[: -len(suffix)]) * factor)
    # bytes
    return int(int(raw) / (1024 * 1024))


def default_channel(package: str) -> str:
    fallback = CHANNEL_FALLBACKS.get(package, "stable")
    pm = oc_json("packagemanifest", package, "-n", "openshift-marketplace")
    if not pm:
        return fallback
    return ((pm.get("status") or {}).get("defaultChannel") or fallback)


def parse_version(version: str) -> tuple[int, int]:
    parts = version.split(".")
    major = int(parts[0]) if parts else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    return major, minor


def is_worker(node: dict[str, Any]) -> bool:
    labels = node.get("metadata", {}).get("labels", {})
    return "node-role.kubernetes.io/worker" in labels


def gpu_noschedule(node: dict[str, Any]) -> bool:
    for taint in node.get("spec", {}).get("taints") or []:
        if taint.get("key") == "nvidia.com/gpu" and taint.get("effect") == "NoSchedule":
            return True
    return False


def allocatable(node: dict[str, Any], resource: str) -> str | None:
    return (node.get("status", {}).get("allocatable") or {}).get(resource)


def probe() -> dict[str, Any]:
    report: dict[str, Any] = {
        "oc_present": shutil.which("oc") is not None,
        "errors": [],
        "warnings": [],
    }
    if not report["oc_present"]:
        report["errors"].append("oc is not on PATH")
        return report

    who = oc("whoami", check=False)
    report["user"] = who.stdout.strip() if who.returncode == 0 else ""
    if who.returncode != 0:
        report["errors"].append("oc whoami failed; log in with oc login first")
        report["is_admin"] = False
        return report

    can = oc("auth", "can-i", "*", "*", "--all-namespaces", check=False)
    report["is_admin"] = can.stdout.strip().lower() == "yes"
    if not report["is_admin"]:
        report["errors"].append("current user is not cluster-admin (oc auth can-i '*' '*' --all-namespaces)")

    cv = oc_json("clusterversion", "version")
    version = ""
    if cv:
        version = (
            ((cv.get("status") or {}).get("desired") or {}).get("version")
            or ((cv.get("status") or {}).get("history") or [{}])[0].get("version")
            or ""
        )
    report["ocp_version"] = version
    if version:
        major_minor = parse_version(version)
        report["ocp_version_ok"] = major_minor >= MIN_OCP
        if not report["ocp_version_ok"]:
            report["errors"].append(
                f"OpenShift {version} is below the required 4.20+"
            )
    else:
        report["ocp_version_ok"] = False
        report["errors"].append("could not read clusterversion")

    nodes_obj = oc_json("nodes") or {"items": []}
    nodes = nodes_obj.get("items") or []
    workers = [n for n in nodes if is_worker(n)]
    if not workers:
        workers = nodes
        report["warnings"].append("no worker role label found; using all nodes")
    report["worker_count"] = len(workers)
    report["worker_count_ok"] = len(workers) >= MIN_WORKERS
    report["worker_count_recommended"] = len(workers) >= RECOMMENDED_WORKERS
    if not report["worker_count_ok"]:
        report["errors"].append(f"need at least {MIN_WORKERS} worker node(s), found {len(workers)}")
    elif not report["worker_count_recommended"]:
        report["warnings"].append(
            f"recommended {RECOMMENDED_WORKERS} workers (GPU + general); found {len(workers)}"
        )

    cpu_alloc = sum(parse_cpu_millis(allocatable(n, "cpu")) for n in workers)
    mem_alloc = sum(parse_memory_mi(allocatable(n, "memory")) for n in workers)
    gpu_alloc = sum(int(allocatable(n, "nvidia.com/gpu") or 0) for n in workers)

    pods_obj = oc_json("pods", "-A", "--field-selector=status.phase=Running") or {"items": []}
    cpu_used = 0
    mem_used = 0
    gpu_used = 0
    for pod in pods_obj.get("items") or []:
        for container in (pod.get("spec") or {}).get("containers") or []:
            req = (container.get("resources") or {}).get("requests") or {}
            cpu_used += parse_cpu_millis(req.get("cpu"))
            mem_used += parse_memory_mi(req.get("memory"))
            gpu_used += int(req.get("nvidia.com/gpu") or 0)

    report["cpu_allocatable_millis"] = cpu_alloc
    report["cpu_free_millis"] = max(0, cpu_alloc - cpu_used)
    report["memory_allocatable_mi"] = mem_alloc
    report["memory_free_mi"] = max(0, mem_alloc - mem_used)
    report["gpu_allocatable"] = gpu_alloc
    report["gpu_free"] = max(0, gpu_alloc - gpu_used)
    report["cpu_ok"] = report["cpu_free_millis"] >= NEED_CPU_MILLIS
    report["memory_ok"] = report["memory_free_mi"] >= NEED_MEMORY_MI
    report["gpu_ok"] = report["gpu_free"] >= NEED_GPU
    report["need_cpu_millis"] = NEED_CPU_MILLIS
    report["need_memory_mi"] = NEED_MEMORY_MI
    report["need_gpu"] = NEED_GPU
    report["need_storage_gi"] = NEED_STORAGE_GI

    nvidia_pci = any(
        (n.get("metadata") or {}).get("labels", {}).get("feature.node.kubernetes.io/pci-10de.present") == "true"
        for n in workers
    )
    report["nvidia_pci_label"] = nvidia_pci

    general_workers = [n for n in workers if not gpu_noschedule(n)]
    report["general_worker_count"] = len(general_workers)
    report["general_worker_ok"] = len(general_workers) >= 1
    if not report["general_worker_ok"] and workers:
        report["errors"].append(
            "every worker has nvidia.com/gpu NoSchedule; engine/UI cannot schedule. "
            "Add a non-GPU worker or untaint one node."
        )

    sc_obj = oc_json("storageclass") or {"items": []}
    storage_classes = sc_obj.get("items") or []
    report["storageclass_count"] = len(storage_classes)
    report["has_default_storageclass"] = any(
        ((sc.get("metadata") or {}).get("annotations") or {}).get(
            "storageclass.kubernetes.io/is-default-class"
        )
        == "true"
        for sc in storage_classes
    )
    if not storage_classes:
        report["errors"].append("no StorageClass found; PVCs for model cache and session export will fail")
    elif not report["has_default_storageclass"]:
        report["warnings"].append("no default StorageClass; set one before PVC bind")

    csv_obj = oc_json("csv", "-A") or {"items": []}
    sub_obj = oc_json("subscription.operators.coreos.com", "-A") or {"items": []}
    operators = []
    missing = []
    for spec in REQUIRED_OPERATORS:
        csv_match = None
        for csv in csv_obj.get("items") or []:
            name = (csv.get("metadata") or {}).get("name") or ""
            if any(name.startswith(prefix) for prefix in spec["csv_prefixes"]):
                csv_match = csv
                break
        sub_match = None
        for sub in sub_obj.get("items") or []:
            if ((sub.get("spec") or {}).get("name") or "") in spec["subscription_names"]:
                sub_match = sub
                break
        phase = ((csv_match or {}).get("status") or {}).get("phase") if csv_match else None
        present = csv_match is not None or sub_match is not None
        succeeded = phase == "Succeeded"
        entry = {
            "id": spec["id"],
            "title": spec["title"],
            "present": present,
            "csv": ((csv_match or {}).get("metadata") or {}).get("name"),
            "phase": phase,
            "ready": succeeded,
        }
        operators.append(entry)
        if not succeeded:
            missing.append(spec["id"])
    report["operators"] = operators
    report["operators_missing"] = missing
    report["operators_ok"] = not missing
    report["operator_channels"] = {
        spec["id"]: default_channel(spec["id"]) for spec in REQUIRED_OPERATORS
    }

    if not report["gpu_ok"]:
        gpu_op_ready = any(o["id"] == "gpu-operator-certified" and o["ready"] for o in operators)
        if nvidia_pci or not gpu_op_ready:
            report["warnings"].append(
                "nvidia.com/gpu not free/allocatable yet; re-check after the NVIDIA GPU Operator is Ready"
            )
        else:
            report["errors"].append(
                f"need {NEED_GPU} free nvidia.com/gpu (allocatable {gpu_alloc}, in use {gpu_used})"
            )
    if not report["cpu_ok"]:
        report["errors"].append(
            f"need {NEED_CPU_MILLIS}m free CPU on workers, have {report['cpu_free_millis']}m"
        )
    if not report["memory_ok"]:
        report["errors"].append(
            f"need {NEED_MEMORY_MI}Mi free memory on workers, have {report['memory_free_mi']}Mi"
        )

    return report


def main() -> int:
    data = probe()
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
