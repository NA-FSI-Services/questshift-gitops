#!/usr/bin/env bash
# QuestShift cluster installer. Facilitator entrypoint — not the in-game terminal.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL="${ROOT}/install"

INSTALL_OPERATORS=false
CHECK_ONLY=false
SKIP_DEPLOY=false
ADD_GPU_NODES=true
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
  --no-add-gpu-nodes    Do not clone a GPU MachineSet when the cluster has no NVIDIA GPU
  --repo-url URL        GitOps repo (default: NA-FSI-Services/questshift-gitops)
  --revision REV        Git revision (default: main)
  -h, --help            Show this help

Prerequisites on this machine: oc, python3, ansible-playbook (ansible-core).
You must already be logged in as cluster-admin (`oc whoami` must succeed).
The installer does not accept cluster API URLs or tokens; keep those in a
local `oc login` / KUBECONFIG and a gitignored `.env`.
Granite 3.2 8B Instruct is copied from the Red Hat AI services ModelCar
catalog by an OpenShift Pipelines (Tekton) PipelineRun onto PVC
questshift-llm-cache (no Hugging Face token, no MinIO/S3). When the
cluster has no NVIDIA GPU, the installer clones a GPU MachineSet
(g6.4xlarge / L4) from the first MachineSet and waits for nvidia.com/gpu.
Pass --no-add-gpu-nodes to skip.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-operators) INSTALL_OPERATORS=true; shift ;;
    --check-only) CHECK_ONLY=true; shift ;;
    --no-add-gpu-nodes) ADD_GPU_NODES=false; shift ;;
    --hf-token)
      echo "Hugging Face tokens are no longer used. Granite weights come from the ModelCar catalog." >&2
      if [[ $# -ge 2 && "${2}" != --* ]]; then
        shift 2
      else
        shift
      fi
      ;;
    --repo-url)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --revision)
      REVISION="${2:-}"
      shift 2
      ;;
    --server|--token|--password|--username|-u|-p)
      echo "The installer does not accept cluster credentials." >&2
      echo "Log in with oc login first. Keep API URLs, tokens, and kubeconfigs out of git." >&2
      exit 2
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

load_local_env() {
  local env_file="${ROOT}/.env"
  local saved_kube
  saved_kube="${KUBECONFIG:-}"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090,SC1091
    source "${env_file}"
    set +a
  fi
  if [[ -n "${saved_kube}" ]]; then
    export KUBECONFIG="${saved_kube}"
  fi
}

require_oc_login() {
  if ! oc whoami >/dev/null 2>&1; then
    echo "Not logged in to OpenShift. Run oc login as cluster-admin for your cluster first." >&2
    echo "./install.sh will not run without an existing oc session." >&2
    echo "Keep API URLs, tokens, kubeconfigs, and CA certificates in local env / a gitignored .env — never in git." >&2
    exit 1
  fi
}

print_ui_route() {
  if [[ "${CHECK_ONLY}" == true ]]; then
    return 0
  fi
  local host=""
  for _ in 1 2 3 4 5 6; do
    host="$(oc get route questshift -n questshift -o jsonpath='{.spec.host}' 2>/dev/null || true)"
    if [[ -n "${host}" ]]; then
      break
    fi
    sleep 5
  done
  echo
  echo "==> QuestShift UI"
  if [[ -n "${host}" ]]; then
    echo "    Open https://${host} to start a campaign."
  else
    echo "    Route not ready yet. After GitOps syncs the UI:"
    echo "      oc get route questshift -n questshift"
  fi
}

need oc
need python3
need ansible-playbook
load_local_env
chmod +x "${INSTALL}/scripts/"*.py 2>/dev/null || true

echo "==> checking oc login"
require_oc_login
echo "  user: $(oc whoami)"

echo "==> probing cluster"
PROBE_JSON="$(python3 "${INSTALL}/scripts/cluster_probe.py")"
MISSING="$(printf '%s' "${PROBE_JSON}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join(d.get("operators_missing") or []))')"
printf '%s' "${PROBE_JSON}" | python3 "${INSTALL}/scripts/cluster_probe.py" --summarize
printf '%s' "${PROBE_JSON}" | python3 "${INSTALL}/scripts/cluster_probe.py" --gate

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

echo "==> running Ansible"
cd "${INSTALL}"
ANSIBLE_NOCOWS=1 ansible-playbook site.yml \
  -e "install_missing_operators=${INSTALL_OPERATORS}" \
  -e "check_only=${CHECK_ONLY}" \
  -e "skip_deploy=${SKIP_DEPLOY}" \
  -e "add_gpu_nodes=${ADD_GPU_NODES}" \
  -e "gitops_repo_url=${REPO_URL}" \
  -e "gitops_revision=${REVISION}"

print_ui_route
