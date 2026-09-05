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

One OpenShift project = one party. Facilitators run `./install.sh` (Ansible). That checks cluster-admin and hardware, optionally installs GitOps / NFD / NVIDIA GPU / RHOAI operators, then syncs `k8s/` with an Argo CD Application.

- LLM Deployment is **vLLM** + `ibm-granite/granite-3.1-8b-instruct` + `nvidia.com/gpu: 1`. No Ollama sidecar. RHOAI is a cluster operator prerequisite, not the Game Master runtime.
- Engine is JVM (not native). UI is nginx static. Campaign YAML is a ConfigMap.
- Hugging Face token secret `questshift-hf` is required for the model pull. The installer creates it with `oc`; git may contain `secretKeyRef` (name + key) only — never a token, `stringData`, or a `Secret` manifest.
- Images are registry placeholders until CI publishes. Do not invent a second Route or session router.
- PVC `questshift-llm-cache` (weights) and `questshift-session-export` (YAML dumps).
- Emergency fallback: `oc apply -k k8s/` after operators and the secret exist.
