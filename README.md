# QuestShift GitOps

OpenShift manifests for one party: UI, Quarkus engine, and vLLM serving IBM Granite 3.2 8B Instruct on a single NVIDIA L4.

## Install

1. Set up an OpenShift **4.20+** cluster (ephemeral workshop clusters are fine; each install is a different cluster).
2. Log in as cluster-admin. `./install.sh` refuses to run unless `oc whoami` succeeds and does not accept API URLs or tokens as flags.
3. Copy `.env.example` to `.env` (gitignored) and set `QUESTSHIFT_HF_TOKEN`.

```bash
oc login --server=https://api.CLUSTER:6443
oc whoami
cp .env.example .env   # never commit
./install.sh
```

Skip the operator prompt and install anything missing:

```bash
export QUESTSHIFT_HF_TOKEN=...   # never commit
./install.sh --install-operators
```

Do not clone a GPU MachineSet when none exist:

```bash
./install.sh --install-operators --no-add-gpu-nodes
```

Validate only: `./install.sh --check-only`

Canonical steps: [INSTALL.md](https://github.com/NA-FSI-Services/questshift/blob/main/docs/INSTALL.md) (local `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/docs/INSTALL.md`).

The Hugging Face token is created as secret `questshift-hf` in namespace `questshift`. Do not commit the token, a Secret YAML, a kubeconfig, a CA certificate, or a specific cluster API URL.

## Files

| File | Purpose |
| --- | --- |
| [install.sh](install.sh) | Facilitator entrypoint (Ansible). Requires an existing `oc` login. |
| [.env.example](.env.example) | Placeholder for gitignored `.env` (`QUESTSHIFT_HF_TOKEN`) |
| [install/](install/) | Probe, operator roles, GitOps deploy |
| [argocd/application.yaml](argocd/application.yaml) | Argo CD Application (synced by the installer) |
| [k8s/llm-deployment.yaml](k8s/llm-deployment.yaml) | vLLM + L4 + PVC |
| [k8s/game-backend-deployment.yaml](k8s/game-backend-deployment.yaml) | Quarkus engine |
| [k8s/game-ui-deployment.yaml](k8s/game-ui-deployment.yaml) | nginx UI |
| [k8s/game-service.yaml](k8s/game-service.yaml) | Services |
| [k8s/openshift-route.yaml](k8s/openshift-route.yaml) | External access |
| [k8s/configmap.yaml](k8s/configmap.yaml) | LLM URL, model id |
| [k8s/pvc.yaml](k8s/pvc.yaml) | Model weights |

Images are placeholders (`image-registry.openshift-image-registry.svc:5000/questshift/...`) until CI publishes builds. Emergency fallback: `oc apply -k k8s/` after operators and `questshift-hf` exist.

## Quality gates

Python 3.11+.

```bash
python3 -m pip install -r requirements-dev.txt
./verify.sh              # yamllint, ruff, shellcheck, kustomize, pytest-cov ≥ 80%
```

Pre-commit (once per clone): `./.githooks/install`. PRs to `main` run **Quality** / **Format, lint, coverage**. Dependabot opens weekly GitHub Actions update PRs.
