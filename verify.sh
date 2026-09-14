#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -x "${ROOT}/.venv/bin/python3" ]]; then
  PYTHON="${ROOT}/.venv/bin/python3"
else
  PYTHON="python3"
fi
"$PYTHON" -m ruff check tools tests install/scripts
"$PYTHON" -m ruff format --check tools tests install/scripts
"$PYTHON" -m yamllint -c .yamllint.yaml k8s/*.yaml argocd
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck install.sh verify.sh .githooks/pre-commit .githooks/install
fi
if command -v kubectl >/dev/null 2>&1; then
  kubectl kustomize k8s >/dev/null
elif command -v kustomize >/dev/null 2>&1; then
  kustomize build k8s >/dev/null
fi
"$PYTHON" -m pytest
"$PYTHON" -m tools.manifests
