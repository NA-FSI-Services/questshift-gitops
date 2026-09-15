from __future__ import annotations

import json
from types import SimpleNamespace

import wait_application
import wait_operator
import wait_pipelinerun


def test_wait_application_usage() -> None:
    assert wait_application.main() == 2


def test_wait_application_healthy(monkeypatch) -> None:
    monkeypatch.setattr(
        wait_application.sys,
        "argv",
        ["wait_application.py", "questshift", "app"],
    )
    payload = {"status": {"health": {"status": "Healthy"}, "sync": {"status": "Synced"}}}
    monkeypatch.setattr(
        wait_application.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    assert wait_application.main() == 0


def test_wait_application_not_synced(monkeypatch) -> None:
    monkeypatch.setattr(
        wait_application.sys,
        "argv",
        ["wait_application.py", "questshift", "app"],
    )
    payload = {"status": {"health": {"status": "Healthy"}, "sync": {"status": "OutOfSync"}}}
    monkeypatch.setattr(
        wait_application.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    assert wait_application.main() == 1


def test_wait_application_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        wait_application.sys,
        "argv",
        ["wait_application.py", "questshift", "app"],
    )
    monkeypatch.setattr(
        wait_application.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="missing"),
    )
    assert wait_application.main() == 1


def test_wait_operator_usage() -> None:
    assert wait_operator.main() == 2


def test_wait_operator_ready(monkeypatch) -> None:
    monkeypatch.setattr(wait_operator.sys, "argv", ["wait_operator.py", "nfd"])
    monkeypatch.setattr(
        wait_operator,
        "probe",
        lambda: {"operators": [{"id": "nfd", "ready": True, "csv": "nfd.v1"}]},
    )
    assert wait_operator.main() == 0


def test_wait_operator_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(wait_operator.sys, "argv", ["wait_operator.py", "nfd"])
    monkeypatch.setattr(wait_operator, "probe", lambda: {"operators": []})
    assert wait_operator.main() == 1


def test_wait_pipelinerun_usage() -> None:
    assert wait_pipelinerun.main() == 2


def test_wait_pipelinerun_succeeded(monkeypatch) -> None:
    monkeypatch.setattr(
        wait_pipelinerun.sys,
        "argv",
        ["wait_pipelinerun.py", "questshift", "questshift-install-granite"],
    )
    payload = {
        "status": {"conditions": [{"type": "Succeeded", "status": "True", "reason": "Succeeded"}]}
    }
    monkeypatch.setattr(
        wait_pipelinerun.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    assert wait_pipelinerun.main() == 0


def test_wait_pipelinerun_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        wait_pipelinerun.sys,
        "argv",
        ["wait_pipelinerun.py", "questshift", "questshift-install-granite"],
    )
    payload = {
        "status": {"conditions": [{"type": "Succeeded", "status": "False", "reason": "Failed"}]}
    }
    monkeypatch.setattr(
        wait_pipelinerun.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    assert wait_pipelinerun.main() == 1


def test_wait_pipelinerun_running(monkeypatch) -> None:
    monkeypatch.setattr(
        wait_pipelinerun.sys,
        "argv",
        ["wait_pipelinerun.py", "questshift", "questshift-install-granite"],
    )
    payload = {"status": {"conditions": [{"type": "Succeeded", "status": "Unknown"}]}}
    monkeypatch.setattr(
        wait_pipelinerun.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    assert wait_pipelinerun.main() == 1
    monkeypatch.setattr(
        wait_pipelinerun.sys,
        "argv",
        ["wait_pipelinerun.py", "questshift", "questshift-install-granite"],
    )
    monkeypatch.setattr(
        wait_pipelinerun.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="missing"),
    )
    assert wait_pipelinerun.main() == 1
