# Agent notes — questshift-gitops

Canonical map:

- GitHub: https://github.com/NA-FSI-Services/questshift/blob/main/AGENTS.md
- Local: `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/AGENTS.md`

Workflows:

- GitHub: https://github.com/NA-FSI-Services/questshift/blob/main/docs/WORKFLOWS.md
- Local: `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/docs/WORKFLOWS.md`

Install:

- GitHub: https://github.com/NA-FSI-Services/questshift/blob/main/docs/INSTALL.md
- Local: `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/docs/INSTALL.md`

## This repo

One OpenShift project = one party. Facilitators `oc login` as cluster-admin, then run `./install.sh` (Ansible). The script refuses to run without that session, checks hardware, optionally installs GitOps / NFD / NVIDIA GPU / RHOAI / OpenShift Pipelines operators, then syncs `k8s/` with an Argo CD Application.

- LLM Deployment is **vLLM** + `ibm-granite/granite-3.2-8b-instruct` + `nvidia.com/gpu: 1`. No Ollama sidecar. RHOAI is a cluster operator prerequisite, not the Game Master runtime. Granite weights come from ModelCar `quay.io/redhat-ai-services/modelcar-catalog:granite-3.2-8b-instruct` via Tekton PipelineRun `questshift-install-granite` (no Hugging Face token, no MinIO).
- Engine is JVM (not native). UI is nginx static. Campaign YAML is a ConfigMap.
- `./install.sh` requires an existing cluster-admin `oc` session. Do not commit workshop API URLs, tokens, kubeconfigs, or CA certs. If NFD sees no NVIDIA GPU, the installer clones a `g6.4xlarge` (L4) MachineSet unless `--no-add-gpu-nodes`.
- Images are registry placeholders until CI publishes. Do not invent a second Route or session router.
- PVC `questshift-llm-cache` (ModelCar weights) and `questshift-session-export` (YAML dumps).
- Emergency fallback: `oc apply -k k8s/` after operators exist.
- Quality: `./verify.sh` (yamllint, ruff, shellcheck, kustomize, pytest-cov ≥ 80% on probe/helpers). Pre-commit: `./.githooks/install`. CI: `.github/workflows/quality.yml`. Dependabot: `.github/dependabot.yml` (weekly GitHub Actions).
