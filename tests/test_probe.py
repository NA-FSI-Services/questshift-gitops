from __future__ import annotations

from types import SimpleNamespace

import cluster_probe


def test_oc_json_none_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        cluster_probe,
        "oc",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="err"),
    )
    assert cluster_probe.oc_json("nodes") is None


def test_oc_json_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        cluster_probe,
        "oc",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="  ", stderr=""),
    )
    assert cluster_probe.oc_json("nodes") is None


def test_oc_json_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        cluster_probe,
        "oc",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"a": 1}', stderr=""),
    )
    assert cluster_probe.oc_json("nodes") == {"a": 1}


def test_oc_invokes_subprocess(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="kubeadmin", stderr="")

    monkeypatch.setattr(cluster_probe.subprocess, "run", fake_run)
    result = cluster_probe.oc("whoami", check=False)
    assert result.stdout == "kubeadmin"
    assert captured["cmd"][0] == "oc"


def test_probe_without_oc(monkeypatch) -> None:
    monkeypatch.setattr(cluster_probe.shutil, "which", lambda _cmd: None)
    report = cluster_probe.probe()
    assert report["oc_present"] is False
    assert report["errors"]


def test_probe_whoami_fails(monkeypatch) -> None:
    monkeypatch.setattr(cluster_probe.shutil, "which", lambda _cmd: "/usr/bin/oc")
    monkeypatch.setattr(
        cluster_probe,
        "oc",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="no"),
    )
    report = cluster_probe.probe()
    assert report["is_admin"] is False
    assert "whoami" in report["errors"][0]


def test_default_channel_fallback(monkeypatch) -> None:
    monkeypatch.setattr(cluster_probe, "oc_json", lambda *a, **k: None)
    assert cluster_probe.default_channel("nfd") == "stable"
    assert cluster_probe.default_channel("unknown-pkg") == "stable"
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        lambda *a, **k: {"status": {"defaultChannel": "fast"}},
    )
    assert cluster_probe.default_channel("nfd") == "fast"


def _ready_csvs() -> dict:
    return {
        "items": [
            {"metadata": {"name": "nfd.v1"}, "status": {"phase": "Succeeded"}},
            {
                "metadata": {"name": "gpu-operator-certified.v1"},
                "status": {"phase": "Succeeded"},
            },
            {
                "metadata": {"name": "openshift-gitops-operator.v1"},
                "status": {"phase": "Succeeded"},
            },
            {"metadata": {"name": "rhods-operator.v1"}, "status": {"phase": "Succeeded"}},
        ]
    }


def _worker(*, gpu: bool = True, tainted: bool = False, pci: bool = True) -> dict:
    labels = {"node-role.kubernetes.io/worker": ""}
    if pci:
        labels["feature.node.kubernetes.io/pci-10de.present"] = "true"
    taints = [{"key": "nvidia.com/gpu", "effect": "NoSchedule"}] if tainted else []
    allocatable = {"cpu": "16", "memory": "64Gi"}
    if gpu:
        allocatable["nvidia.com/gpu"] = "1"
    return {
        "metadata": {"labels": labels},
        "spec": {"taints": taints},
        "status": {"allocatable": allocatable},
    }


def _oc_json_factory(overrides: dict | None = None):
    data = {
        "clusterversion": {"status": {"desired": {"version": "4.20.1"}}},
        "nodes": {"items": [_worker(), _worker(gpu=False, pci=False)]},
        "pods": {
            "items": [
                {
                    "spec": {
                        "containers": [
                            {
                                "resources": {
                                    "requests": {
                                        "cpu": "100m",
                                        "memory": "128Mi",
                                        "nvidia.com/gpu": "0",
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        },
        "storageclass": {
            "items": [
                {
                    "metadata": {
                        "annotations": {"storageclass.kubernetes.io/is-default-class": "true"}
                    }
                }
            ]
        },
        "csv": _ready_csvs(),
        "subscription.operators.coreos.com": {
            "items": [{"spec": {"name": "nfd"}}],
        },
        "packagemanifest": {"status": {"defaultChannel": "stable"}},
    }
    if overrides:
        data.update(overrides)

    def fake(*args: str):
        key = args[0]
        return data.get(key)

    return fake


def _login_ok(monkeypatch, admin: str = "yes") -> None:
    monkeypatch.setattr(cluster_probe.shutil, "which", lambda _cmd: "/usr/bin/oc")

    def fake_oc(*args: str, check: bool = True):
        if args[0] == "whoami":
            return SimpleNamespace(returncode=0, stdout="kubeadmin\n", stderr="")
        if args[0] == "auth":
            return SimpleNamespace(returncode=0, stdout=f"{admin}\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cluster_probe, "oc", fake_oc)


def test_probe_healthy_cluster(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(cluster_probe, "oc_json", _oc_json_factory())
    report = cluster_probe.probe()
    assert report["is_admin"] is True
    assert report["ocp_version_ok"] is True
    assert report["cpu_ok"] is True
    assert report["memory_ok"] is True
    assert report["gpu_ok"] is True
    assert report["operators_ok"] is True
    assert report["has_default_storageclass"] is True


def test_probe_not_admin_and_old_version(monkeypatch) -> None:
    _login_ok(monkeypatch, admin="no")
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory(
            {
                "clusterversion": {"status": {"desired": {"version": "4.19.0"}}},
            }
        ),
    )
    report = cluster_probe.probe()
    assert report["is_admin"] is False
    assert report["ocp_version_ok"] is False
    assert any("cluster-admin" in e for e in report["errors"])
    assert any("4.20+" in e for e in report["errors"])


def test_probe_missing_clusterversion(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(cluster_probe, "oc_json", _oc_json_factory({"clusterversion": None}))
    report = cluster_probe.probe()
    assert report["ocp_version_ok"] is False


def test_probe_version_from_history(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory(
            {
                "clusterversion": {"status": {"history": [{"version": "4.20.9"}]}},
            }
        ),
    )
    report = cluster_probe.probe()
    assert report["ocp_version"] == "4.20.9"


def test_probe_no_worker_labels(monkeypatch) -> None:
    _login_ok(monkeypatch)
    unlabeled = _worker()
    unlabeled["metadata"]["labels"] = {}
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory({"nodes": {"items": [unlabeled]}}),
    )
    report = cluster_probe.probe()
    assert report["warnings"]
    assert report["worker_count"] == 1


def test_probe_no_nodes(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory({"nodes": {"items": []}}),
    )
    report = cluster_probe.probe()
    assert report["worker_count_ok"] is False


def test_probe_all_gpu_tainted(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory({"nodes": {"items": [_worker(tainted=True)]}}),
    )
    report = cluster_probe.probe()
    assert report["general_worker_ok"] is False
    assert any("NoSchedule" in e for e in report["errors"])


def test_probe_storage_and_capacity_errors(monkeypatch) -> None:
    _login_ok(monkeypatch)
    tiny = _worker(gpu=False, pci=False)
    tiny["status"]["allocatable"] = {"cpu": "100m", "memory": "64Mi"}
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory(
            {
                "nodes": {"items": [tiny]},
                "storageclass": {"items": []},
            }
        ),
    )
    report = cluster_probe.probe()
    assert report["cpu_ok"] is False
    assert report["memory_ok"] is False
    assert report["gpu_ok"] is False
    assert any("StorageClass" in e for e in report["errors"])
    assert any("CPU" in e for e in report["errors"])
    assert any("memory" in e for e in report["errors"])
    assert any("nvidia.com/gpu" in e for e in report["errors"])


def test_probe_gpu_warning_when_operator_not_ready(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory(
            {
                "nodes": {"items": [_worker(gpu=False)]},
                "csv": {"items": []},
                "subscription.operators.coreos.com": {"items": []},
            }
        ),
    )
    report = cluster_probe.probe()
    assert report["gpu_ok"] is False
    assert any("GPU Operator" in w for w in report["warnings"])


def test_probe_storageclass_without_default(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory({"storageclass": {"items": [{"metadata": {"annotations": {}}}]}}),
    )
    report = cluster_probe.probe()
    assert report["has_default_storageclass"] is False
    assert any("default StorageClass" in w for w in report["warnings"])


def test_probe_single_worker_recommended_warning(monkeypatch) -> None:
    _login_ok(monkeypatch)
    monkeypatch.setattr(
        cluster_probe,
        "oc_json",
        _oc_json_factory({"nodes": {"items": [_worker(), _worker(gpu=False, pci=False)][:1]}}),
    )
    report = cluster_probe.probe()
    assert report["worker_count_ok"] is True
    assert report["worker_count_recommended"] is False


def test_main_dumps_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cluster_probe, "probe", lambda: {"ok": True})
    assert cluster_probe.main() == 0
    assert "ok" in capsys.readouterr().out
