# QuestShift GitOps

OpenShift manifests for one party deployment: UI, Quarkus engine, and vLLM serving IBM Granite 3.1 8B Instruct on a single NVIDIA L4.

## Apply

```bash
oc new-project questshift
# Hugging Face token is required for ibm-granite/granite-3.1-8b-instruct.
# Create the secret on the cluster. Do not commit the token or a Secret YAML.
oc create secret generic questshift-hf --from-literal=token=YOUR_HF_TOKEN
oc apply -k k8s/
```

GPU operator and NVIDIA L4 node must already be present. The LLM pod requests `nvidia.com/gpu: 1`.

## Files

| File | Purpose |
| --- | --- |
| [k8s/llm-deployment.yaml](k8s/llm-deployment.yaml) | vLLM + L4 + PVC |
| [k8s/game-backend-deployment.yaml](k8s/game-backend-deployment.yaml) | Quarkus engine |
| [k8s/game-ui-deployment.yaml](k8s/game-ui-deployment.yaml) | nginx UI |
| [k8s/game-service.yaml](k8s/game-service.yaml) | Services |
| [k8s/openshift-route.yaml](k8s/openshift-route.yaml) | External access |
| [k8s/configmap.yaml](k8s/configmap.yaml) | LLM URL, model id |
| [k8s/pvc.yaml](k8s/pvc.yaml) | Model weights |

Images are placeholders (`image-registry.openshift-image-registry.svc:5000/questshift/...`) until CI publishes builds.
