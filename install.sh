#!/usr/bin/env bash
# QuestShift cluster installer. Facilitator entrypoint — not the in-game terminal.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL="${ROOT}/install"

INSTALL_OPERATORS=false
CHECK_ONLY=false
SKIP_DEPLOY=false
HF_TOKEN=""
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
You must already be logged in as cluster-admin (`oc whoami` must succeed).
The installer does not accept cluster API URLs or tokens; keep those in a
local `oc login` / KUBECONFIG and a gitignored `.env`.
`--install-operators` without QUESTSHIFT_HF_TOKEN installs operators only.
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
  local saved_hf saved_kube
  saved_hf="${QUESTSHIFT_HF_TOKEN:-}"
  saved_kube="${KUBECONFIG:-}"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090,SC1091
    source "${env_file}"
    set +a
  fi
  if [[ -n "${saved_hf}" ]]; then
    export QUESTSHIFT_HF_TOKEN="${saved_hf}"
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

need oc
need python3
need ansible-playbook
load_local_env
if [[ -z "${HF_TOKEN}" ]]; then
  HF_TOKEN="${QUESTSHIFT_HF_TOKEN:-}"
fi
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

if [[ "${CHECK_ONLY}" != true && -z "${HF_TOKEN}" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "Hugging Face token for ibm-granite/granite-3.2-8b-instruct (input hidden): " HF_TOKEN
    echo
  fi
  if [[ -z "${HF_TOKEN}" ]]; then
    if [[ "${INSTALL_OPERATORS}" == true ]]; then
      echo "No Hugging Face token; installing operators only. Re-run with QUESTSHIFT_HF_TOKEN in a gitignored .env to deploy."
      SKIP_DEPLOY=true
    else
      echo "A Hugging Face token is required. Set QUESTSHIFT_HF_TOKEN in a gitignored .env or pass --hf-token." >&2
      exit 1
    fi
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
  -e "skip_deploy=${SKIP_DEPLOY}" \
  -e "gitops_repo_url=${REPO_URL}" \
  -e "gitops_revision=${REVISION}"
