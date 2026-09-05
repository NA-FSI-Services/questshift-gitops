#!/usr/bin/env bash
# QuestShift cluster installer. Facilitator entrypoint — not the in-game terminal.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL="${ROOT}/install"

INSTALL_OPERATORS=false
CHECK_ONLY=false
HF_TOKEN="${QUESTSHIFT_HF_TOKEN:-}"
REPO_URL="https://github.com/NA-FSI-Services/questshift-gitops"
REVISION="main"

usage() {
  cat <<'EOF'
QuestShift installer

  ./install.sh
  ./install.sh --install-operators
  ./install.sh --check-only

Options:
  --install-operators   Install missing operators without prompting
  --check-only          Validate access, hardware, and operators; do not deploy
  --hf-token TOKEN      Hugging Face token (prefer QUESTSHIFT_HF_TOKEN; argv is visible in ps)
  --repo-url URL        GitOps repo (default: NA-FSI-Services/questshift-gitops)
  --revision REV        Git revision (default: main)
  -h, --help            Show this help

Prerequisites on this machine: oc, python3, ansible-playbook (ansible-core).
Log in as cluster-admin first: oc login ...
The Hugging Face token is applied as secret questshift-hf and is never committed.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-operators) INSTALL_OPERATORS=true; shift ;;
    --check-only) CHECK_ONLY=true; shift ;;
    --hf-token)
      HF_TOKEN="${2:-}"
      shift 2
      ;;
    --repo-url)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --revision)
      REVISION="${2:-}"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

need oc
need python3
need ansible-playbook
chmod +x "${INSTALL}/scripts/"*.py 2>/dev/null || true

echo "==> probing cluster"
PROBE_JSON="$(python3 "${INSTALL}/scripts/cluster_probe.py")"
MISSING="$(printf '%s' "${PROBE_JSON}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join(d.get("operators_missing") or []))')"
printf '%s' "${PROBE_JSON}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
print(f"  user:              {data.get(\"user\")}")
print(f"  cluster-admin:     {data.get(\"is_admin\")}")
print(f"  openshift:         {data.get(\"ocp_version\")}")
print(f"  workers:           {data.get(\"worker_count\")}")
print(f"  free CPU (m):      {data.get(\"cpu_free_millis\")} (need {data.get(\"need_cpu_millis\")})")
print(f"  free memory (Mi):  {data.get(\"memory_free_mi\")} (need {data.get(\"need_memory_mi\")})")
print(f"  free GPU:          {data.get(\"gpu_free\")} (need {data.get(\"need_gpu\")})")
print("  operators:")
for op in data.get("operators") or []:
    state = "ready" if op.get("ready") else ("present" if op.get("present") else "missing")
    print(f"    - {op[\"title\"]}: {state}")
if data.get("warnings"):
    print("  warnings:")
    for warning in data["warnings"]:
        print(f"    - {warning}")
if data.get("errors"):
    print("  probe notes:")
    for err in data["errors"]:
        print(f"    - {err}")
'

printf '%s' "${PROBE_JSON}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
bad = []
if not data.get("is_admin"):
    bad.append("current user is not cluster-admin")
if data.get("ocp_version_ok") is False:
    bad.append("OpenShift must be 4.20+")
if data.get("worker_count_ok") is False:
    bad.append("need at least 1 worker node")
if data.get("general_worker_ok") is False:
    bad.append("need a worker without nvidia.com/gpu NoSchedule for engine/UI")
if data.get("cpu_ok") is False:
    bad.append("not enough free CPU on workers")
if data.get("memory_ok") is False:
    bad.append("not enough free memory on workers")
if int(data.get("storageclass_count") or 0) == 0:
    bad.append("no StorageClass found")
if bad:
    print("refusing to continue: " + "; ".join(bad), file=sys.stderr)
    sys.exit(1)
'

if [[ -n "${MISSING}" && "${INSTALL_OPERATORS}" != true && "${CHECK_ONLY}" != true ]]; then
  echo
  echo "Missing operators: ${MISSING}"
  if [[ -t 0 ]]; then
    read -r -p "Install missing operators now? [y/N] " answer
    case "${answer}" in
      y|Y|yes|YES) INSTALL_OPERATORS=true ;;
      *)
        echo "Refusing to continue. Re-run with --install-operators, or install the operators yourself."
        exit 1
        ;;
    esac
  else
    echo "Non-interactive session. Re-run with --install-operators."
    exit 1
  fi
fi

if [[ "${CHECK_ONLY}" != true && -z "${HF_TOKEN}" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "Hugging Face token for ibm-granite/granite-3.1-8b-instruct (input hidden): " HF_TOKEN
    echo
  fi
  if [[ -z "${HF_TOKEN}" ]]; then
    echo "A Hugging Face token is required. Pass --hf-token or QUESTSHIFT_HF_TOKEN." >&2
    exit 1
  fi
fi

if [[ -n "${HF_TOKEN}" ]]; then
  export QUESTSHIFT_HF_TOKEN="${HF_TOKEN}"
fi

echo "==> running Ansible"
cd "${INSTALL}"
ANSIBLE_NOCOWS=1 ansible-playbook site.yml \
  -e "install_missing_operators=${INSTALL_OPERATORS}" \
  -e "check_only=${CHECK_ONLY}" \
  -e "gitops_repo_url=${REPO_URL}" \
  -e "gitops_revision=${REVISION}"
