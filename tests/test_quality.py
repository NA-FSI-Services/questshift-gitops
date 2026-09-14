from __future__ import annotations

from pathlib import Path

import pytest
from cluster_probe import (
    allocatable,
    gpu_noschedule,
    is_worker,
    parse_cpu_millis,
    parse_memory_mi,
    parse_version,
)

from tools.manifests import main, validate_manifests

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_TOKENS = """\
vllm
ibm-granite/granite-3.1-8b-instruct
nvidia.com/gpu: "1"
questshift-hf
"""


def test_parse_cpu_millis() -> None:
    assert parse_cpu_millis(None) == 0
    assert parse_cpu_millis("250m") == 250
    assert parse_cpu_millis("2") == 2000
    assert parse_cpu_millis("1000000000n") == 1000


def test_parse_memory_mi() -> None:
    assert parse_memory_mi(None) == 0
    assert parse_memory_mi("512Mi") == 512
    assert parse_memory_mi("1Gi") == 1024
    assert parse_memory_mi("1Ti") == 1024 * 1024
    assert parse_memory_mi("1024Ki") == 1
    assert parse_memory_mi("1G") == 1024
    assert parse_memory_mi("1048576") == 1


def test_parse_version_and_workers() -> None:
    assert parse_version("4.20.1") == (4, 20)
    assert parse_version("4") == (4, 0)
    node = {"metadata": {"labels": {"node-role.kubernetes.io/worker": ""}}}
    assert is_worker(node)
    assert not is_worker({"metadata": {"labels": {}}})


def test_gpu_taint_and_allocatable() -> None:
    tainted = {"spec": {"taints": [{"key": "nvidia.com/gpu", "effect": "NoSchedule"}]}}
    assert gpu_noschedule(tainted)
    assert not gpu_noschedule({"spec": {}})
    assert not gpu_noschedule({"spec": {"taints": [{"key": "other"}]}})
    node = {"status": {"allocatable": {"cpu": "2", "nvidia.com/gpu": "1"}}}
    assert allocatable(node, "cpu") == "2"
    assert allocatable({"status": {}}, "cpu") is None


def test_manifests_pass() -> None:
    validate_manifests(ROOT / "k8s")
    assert main() == 0


def test_manifests_reject_secret(tmp_path: Path) -> None:
    (tmp_path / "secret.yaml").write_text(
        "kind: Secret\nstringData:\n  token: x\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="forbidden"):
        validate_manifests(tmp_path)


def test_manifests_reject_ollama(tmp_path: Path) -> None:
    (tmp_path / "llm.yaml").write_text(CANONICAL_TOKENS + "ollama\n", encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden"):
        validate_manifests(tmp_path)


def test_manifests_reject_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no manifests"):
        validate_manifests(tmp_path)


def test_manifests_missing_required(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("kind: Deployment\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required"):
        validate_manifests(tmp_path)


def test_manifests_gpu_must_be_one(tmp_path: Path) -> None:
    blob = CANONICAL_TOKENS.replace('nvidia.com/gpu: "1"', "nvidia.com/gpu: 2")
    (tmp_path / "a.yaml").write_text(blob, encoding="utf-8")
    with pytest.raises(ValueError, match="GPU"):
        validate_manifests(tmp_path)
