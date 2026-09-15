from __future__ import annotations

import json
from types import SimpleNamespace

import ensure_gpu_machineset as gpu_ms


def _donor(*, name: str = "cluster-worker", instance_type: str = "m6a.xlarge") -> dict:
    return {
        "apiVersion": "machine.openshift.io/v1beta1",
        "kind": "MachineSet",
        "metadata": {
            "name": name,
            "namespace": "openshift-machine-api",
            "uid": "drop-me",
            "resourceVersion": "99",
            "generation": 3,
            "creationTimestamp": "2026-01-01T00:00:00Z",
            "managedFields": [{"manager": "oc"}],
            "annotations": {
                "kubectl.kubernetes.io/last-applied-configuration": "{secret}",
                "keep": "yes",
            },
            "labels": {"machine.openshift.io/cluster-api-machineset": name},
        },
        "spec": {
            "replicas": 3,
            "selector": {"matchLabels": {"machine.openshift.io/cluster-api-machineset": name}},
            "template": {
                "metadata": {
                    "labels": {"machine.openshift.io/cluster-api-machineset": name},
                },
                "spec": {
                    "providerSpec": {
                        "value": {
                            "instanceType": instance_type,
                            "ami": {"id": "ami-local-only"},
                        }
                    }
                },
            },
        },
        "status": {"replicas": 3},
    }


def test_gpu_machineset_name() -> None:
    assert gpu_ms.gpu_machineset_name("worker") == "worker-gpu"
    assert gpu_ms.gpu_machineset_name("worker-gpu") == "worker-gpu"


def test_transform_sets_l4_type_taint_and_strips_identity() -> None:
    out = gpu_ms.gpu_machineset_from_donor(_donor(), instance_type="g6.4xlarge")
    md = out["metadata"]
    assert md["name"] == "cluster-worker-gpu"
    assert "uid" not in md
    assert "status" not in out
    assert "last-applied-configuration" not in (md.get("annotations") or {})
    assert md["annotations"]["keep"] == "yes"
    assert out["spec"]["replicas"] == 1
    label = "machine.openshift.io/cluster-api-machineset"
    assert md["labels"][label] == "cluster-worker-gpu"
    assert out["spec"]["selector"]["matchLabels"][label] == "cluster-worker-gpu"
    assert out["spec"]["template"]["metadata"]["labels"][label] == "cluster-worker-gpu"
    provider = out["spec"]["template"]["spec"]["providerSpec"]["value"]
    assert provider["instanceType"] == "g6.4xlarge"
    assert provider["ami"]["id"] == "ami-local-only"
    assert out["spec"]["template"]["spec"]["taints"] == [
        {"key": "nvidia.com/gpu", "value": "present", "effect": "NoSchedule"}
    ]


def test_transform_requires_aws_instance_type() -> None:
    donor = _donor()
    del donor["spec"]["template"]["spec"]["providerSpec"]["value"]["instanceType"]
    try:
        gpu_ms.gpu_machineset_from_donor(donor)
    except ValueError as exc:
        assert "instanceType" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_transform_requires_name() -> None:
    try:
        gpu_ms.gpu_machineset_from_donor({"metadata": {}})
    except ValueError as exc:
        assert "metadata.name" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_ensure_skips_via_probe(monkeypatch) -> None:
    monkeypatch.setattr(gpu_ms, "probe", lambda: {"nvidia_pci_label": True, "gpu_allocatable": 0})
    result = gpu_ms.ensure_gpu_machineset(apply=True)
    assert result["action"] == "skipped"


def test_oc_apply_doc_passes_stdin(monkeypatch) -> None:
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(gpu_ms.subprocess, "run", fake_run)
    gpu_ms.oc_apply_doc({"kind": "MachineSet"})
    assert captured["cmd"][:3] == ["oc", "apply", "-f"]
    assert "MachineSet" in captured["input"]


def test_ensure_fails_without_machinesets(monkeypatch) -> None:
    monkeypatch.setattr(gpu_ms, "load_machinesets", lambda: [])
    try:
        gpu_ms.ensure_gpu_machineset(already_has_gpu=False)
    except RuntimeError as exc:
        assert "no MachineSets" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_ensure_dry_run_does_not_apply(monkeypatch) -> None:
    monkeypatch.setattr(gpu_ms, "load_machinesets", lambda: [_donor()])
    called = {"apply": False}

    def boom(_doc):
        called["apply"] = True
        raise AssertionError("apply should not run")

    monkeypatch.setattr(gpu_ms, "oc_apply_doc", boom)
    result = gpu_ms.ensure_gpu_machineset(already_has_gpu=False, apply=False)
    assert result["action"] == "planned"
    assert result["name"] == "cluster-worker-gpu"
    assert result["instanceType"] == "g6.4xlarge"
    assert called["apply"] is False


def test_ensure_applies(monkeypatch) -> None:
    monkeypatch.setattr(gpu_ms, "load_machinesets", lambda: [_donor()])
    captured: dict = {}

    def fake_apply(doc):
        captured["name"] = doc["metadata"]["name"]
        captured["type"] = doc["spec"]["template"]["spec"]["providerSpec"]["value"]["instanceType"]
        return SimpleNamespace(returncode=0, stdout="created", stderr="")

    monkeypatch.setattr(gpu_ms, "oc_apply_doc", fake_apply)
    result = gpu_ms.ensure_gpu_machineset(
        already_has_gpu=False, apply=True, instance_type="g6.4xlarge"
    )
    assert result["action"] == "applied"
    assert captured["name"] == "cluster-worker-gpu"
    assert captured["type"] == "g6.4xlarge"


def test_ensure_apply_error(monkeypatch) -> None:
    monkeypatch.setattr(gpu_ms, "load_machinesets", lambda: [_donor()])
    monkeypatch.setattr(
        gpu_ms,
        "oc_apply_doc",
        lambda _d: SimpleNamespace(returncode=1, stdout="", stderr="denied"),
    )
    try:
        gpu_ms.ensure_gpu_machineset(already_has_gpu=False)
    except RuntimeError as exc:
        assert "denied" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_main_dry_run(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        gpu_ms,
        "ensure_gpu_machineset",
        lambda **k: {"action": "planned", "name": "worker-gpu"},
    )
    assert gpu_ms.main(["--dry-run", "--instance-type", "g6.4xlarge"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "worker-gpu"


def test_main_error(monkeypatch, capsys) -> None:
    def boom(**_k):
        raise RuntimeError("no MachineSets")

    monkeypatch.setattr(gpu_ms, "ensure_gpu_machineset", boom)
    assert gpu_ms.main([]) == 1
    assert "no MachineSets" in capsys.readouterr().err


def test_load_machinesets_empty(monkeypatch) -> None:
    monkeypatch.setattr(gpu_ms, "oc_json", lambda *a: None)
    assert gpu_ms.load_machinesets() == []
    monkeypatch.setattr(gpu_ms, "oc_json", lambda *a: {"items": [_donor()]})
    assert len(gpu_ms.load_machinesets()) == 1
