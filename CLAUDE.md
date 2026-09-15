# Claude / Cursor — questshift-gitops

Read `AGENTS.md` first (this repo), then the docs-repo map.

- GitHub: https://github.com/NA-FSI-Services/questshift/blob/main/AGENTS.md
- Local: `/Users/dtorresf/Documents/GitHub/na-fsi-services/questshift/questshift/AGENTS.md`

## Hard rules (v1 freeze)

- One party per deployment. No multi-tenant router.
- vLLM only, Granite 3.2 8B Instruct, NVIDIA L4 (`nvidia.com/gpu: 1`). No Ollama.
- Engine JVM, UI nginx. No native image build in this repo.
- Terminal remains simulated in the engine; these manifests must not add a login node or privileged command runner.
- Apply with `./install.sh` (OpenShift GitOps Application) after `oc login`. The script does not take cluster API URLs or tokens. `--no-add-gpu-nodes` skips cloning a GPU MachineSet. `oc apply -k k8s/` is fallback only. Keep GPU request exactly `1`.
- Granite weights come from the Red Hat AI services ModelCar catalog via Tekton (`k8s/granite-pipeline.yaml`). Do not add MinIO, a Hugging Face token, `questshift-hf`, or a `Secret` YAML with `stringData`. Never commit kubeconfigs, CA certs, or workshop API URLs.
- v1 non-goals: TTS pods, extra campaigns, extra Routes.
- Quality: `./verify.sh` (yamllint, ruff, shellcheck, kustomize, pytest-cov). Pre-commit: `./.githooks/install`.
