# QuestShift GitOps

OpenShift manifests for one party: UI, Quarkus engine, and vLLM serving IBM Granite 3.1 8B Instruct on a single NVIDIA L4.

## Install

1. Set up an OpenShift **4.20+** cluster.
2. Run the installer (cluster-admin `oc` session):

```bash
oc login --server=https://api.CLUSTER:6443
./install.sh
```

Skip the operator prompt and install anything missing:

```bash
export QUESTSHIFT_HF_TOKEN=...   # never commit
./install.sh --install-operators
```

Validate only: `./install.sh --check-only`

Canonical steps: [INSTALL.md](https://github.com/NA-FSI-Services/questshift/blob/main/docs/INSTALL.md) (local `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/docs/INSTALL.md`).

The Hugging Face token is created as secret `questshift-hf` in namespace `questshift`. Do not commit the token or a Secret YAML.

## Files

| File | Purpose |
| --- | --- |
| [install.sh](install.sh) | Facilitator entrypoint (Ansible) |
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
