# ABRIS

ABRIS is an OpenCode-native bioinformatics AI system scaffold.

OpenCode is the embedded kernel. ABRIS is the product and domain layer that governs bioinformatics workflows, safety, acquisition, and skills on top of that kernel.

The design still follows a six-layer architecture:

- Layer 0: environment adaptation
- Layer 1: atomic skills
- Layer 2: analysis pipelines
- Layer 3: orchestration and scheduling
- Layer 4: data loop and knowledge accumulation
- Layer 5: intelligent research and discovery

## Project Layout

```text
src/abris/
configs/
packages/opencode-bridge/
design-docs/
tests/
```

## Target State

The intended end-state is:

- OpenCode embedded internally as the isolated runtime kernel
- ABRIS as the bioinformatics product layer over that kernel
- long-duration autonomous work with checkpoint, resume, review, and failure policy
- autonomous but policy-bounded research-boundary discovery
- autonomous but policy-bounded external data acquisition from approved sources
- skills-guided code generation and optimization with review and audit gates
- sequencing-company data intake, validation, adaptation, and analysis

## Current Scope

The current code is still intentionally minimal, but it is now oriented toward the OpenCode-kernel-first target above rather than toward a standalone ABRIS runtime.

Runtime direction:

- OpenCode is the embedded kernel and tool/runtime center
- ABRIS is the bioinformatics product and policy layer on top of OpenCode
- Python owns domain logic, pipeline planning, and tool adaptation
- OpenCode SDK is the default integration path
- OpenCode plugins are the preferred customization path
- Direct OpenCode core modification is the last resort
- All design documents live under `design-docs/` and are ignored by Git

## Design Docs

- `design-docs/architecture-principles.md`
- `design-docs/opencode-integration.md`
- `design-docs/pipeline-planning-spec.md`
- `design-docs/skills-spec.md`
- `design-docs/skill-manifest-yaml-spec.md`
- `design-docs/sequencing-safety-policy.md`
- `design-docs/sequencing-gateway-design.md`
- `design-docs/autonomy-governance-spec.md`

## Implemented Now

- bounded OpenCode runtime bridge and lifecycle surface
- file-intake safety and environment-aware pre-execution blocking
- config-backed pipeline loading and validation
- orchestrator baseline and tests

## Deferred for Later Phases

- bounded external data acquisition policy enforcement in code
- skills-guided code generation and optimization loops
- durable long-running autonomy with checkpoint and resume
- real bioinformatics tool adapters

## Quick Start

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m abris.cli
```

```bash
cd packages/opencode-bridge
npm install
npm run build
```

## Run from Any Git Bash Directory

One-time install from the repo root:

```bash
python -m pip install -e .
```

Then, from any Git Bash directory, start the local UI with:

```bash
abris-ui
```

Default launcher behavior:

- enables OpenCode runtime (`ABRIS_USE_OPENCODE=1`)
- enables repo-local paper-search MCP (`ABRIS_ENABLE_PAPER_SEARCH_MCP=1`)
- uses bounded local policy defaults
- starts the control plane on `127.0.0.1:18080`

Override host/port or auth the same way as the raw control-plane entrypoint:

```bash
abris-ui --host 127.0.0.1 --port 18081 --username admin --password abris-admin
```

If Git Bash cannot find `abris-ui`, ensure the Python Scripts directory for the interpreter used by `python -m pip install -e .` is on your `PATH`.

## Near-Term Build Order

1. Make embedded OpenCode the default kernel path instead of an optional helper path
2. Add bounded autonomy governance to planning and runtime execution
3. Add atomic skill manifests and file-based registry loading
4. Add source-governed external data acquisition flow
5. Add skills-guided code generation and optimization flow
6. Add adapters for Python, R, CLI, Docker, and Conda
7. Build the first runnable RNA-seq workflow against real controlled inputs
