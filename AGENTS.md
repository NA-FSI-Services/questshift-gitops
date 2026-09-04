# Agent notes — questshift-gitops

Canonical map:

- GitHub: https://github.com/NA-FSI-Services/questshift/blob/main/AGENTS.md
- Local: `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/AGENTS.md`

Workflows:

- GitHub: https://github.com/NA-FSI-Services/questshift/blob/main/docs/WORKFLOWS.md
- Local: `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/docs/WORKFLOWS.md`

## This repo

One OpenShift project = one party. `oc apply -k k8s/`.

- LLM Deployment is **vLLM** + `ibm-granite/granite-3.1-8b-instruct` + `nvidia.com/gpu: 1`. No Ollama sidecar.
- Engine is JVM (not native). UI is nginx static. Campaign YAML is a ConfigMap.
- Hugging Face token secret `questshift-hf` is required for the model pull. Create it on the cluster with `oc create secret generic questshift-hf --from-literal=token=...`. Git may contain `secretKeyRef` (name + key) only — never a token, `stringData`, or a `Secret` manifest.
- Images are registry placeholders until CI publishes. Do not invent a second Route or session router.
- PVC `questshift-llm-cache` (weights) and `questshift-session-export` (YAML dumps).
