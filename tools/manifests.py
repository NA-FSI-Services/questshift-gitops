"""QuestShift GitOps freeze checks: no secrets, vLLM-only, one GPU."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN = (
    "stringData:",
    "ollama",
    "kind: Secret",
)
REQUIRED = (
    "ibm-granite/granite-3.2-8b-instruct",
    "vllm",
    "nvidia.com/gpu",
    "questshift-hf",
)


def iter_manifests(k8s_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.yaml", "*.yml"):
        files.extend(p for p in k8s_dir.rglob(pattern) if p.is_file())
    return sorted(files)


def _has_gpu_one(blob: str) -> bool:
    return (
        'nvidia.com/gpu: "1"' in blob
        or "nvidia.com/gpu: '1'" in blob
        or "nvidia.com/gpu: 1" in blob
    )


def validate_manifests(k8s_dir: Path) -> None:
    files = iter_manifests(k8s_dir)
    if not files:
        raise ValueError(f"no manifests under {k8s_dir}")
    blob = "\n".join(p.read_text(encoding="utf-8") for p in files)
    lower = blob.lower()
    for token in FORBIDDEN:
        if token.lower() in lower:
            raise ValueError(f"forbidden token in k8s manifests: {token}")
    for token in REQUIRED:
        if token.lower() not in lower:
            raise ValueError(f"missing required token in k8s manifests: {token}")
    if not _has_gpu_one(blob):
        raise ValueError("LLM GPU request must be 1")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    validate_manifests(root / "k8s")
    print("gitops manifests ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
