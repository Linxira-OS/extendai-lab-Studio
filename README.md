# extendai-lab-Studio

extendai-lab-Studio is the orchestration and automation layer for AI-driven scientific research. It runs on top of OpenCode as the embedded kernel, coordinates multiple LLMs to execute complex research workflows, and delegates domain-specific work to external skill repositories.

## Positioning

extendai-lab-Studio is **not** a skill library. It is the system that orchestrates skills, models, and tools into end-to-end research pipelines.

| Project | Role |
|---------|------|
| **extendai-lab-Studio** (this repo) | Orchestration layer — multi-model coordination, pipeline planning, autonomy governance, control plane |
| [openagent-labforge](https://github.com/Linxira-OS/openagent-labforge) | OpenCode ecosystem — runtime framework, plugin system, SDK integration |
| [bioSkills](https://github.com/BOHUYESHAN-APB/bioSkills) | Bioinformatics skills — 400+ SKILL.md patterns for genomics, transcriptomics, proteomics, etc. |
| [ChemClaw](https://github.com/BOHUYESHAN-APB/ChemClaw) | Chemistry skills — molecular simulation, spectra prediction, ADMET, chemical file conversion |
| [ClawBio](https://github.com/BOHUYESHAN-APB/ClawBio) | Bioinformatics execution — 59 executable skills with orchestrator, reproducibility bundles, and tests |

## Architecture

Six-layer design:

- **Layer 0** — Environment adaptation and file-intake safety
- **Layer 1** — Atomic skill loading from external repositories
- **Layer 2** — Analysis pipeline planning and validation
- **Layer 3** — Multi-model orchestration and scheduling
- **Layer 4** — Data loop, run logging, and knowledge accumulation
- **Layer 5** — Autonomous research discovery

## Multi-Model Strategy

The system coordinates multiple LLMs, each assigned a specific role:

- **DeepSeek V4 Pro** — primary code executor and task commander (1M context, no native multimodal)
- **MiMo 2.5 Pro** — fast reviewer and task dispatcher (cost-effective, TTS support)
- **MiMo 2.5 Standard** — multimodal literature analysis (native image recognition)
- **DeepSeek V4 Flash** — parallel search and tool calling (paper search, academic search)
- **Gemma 4 27B** (local) — external vision module for DS Pro
- **Gemini 3.1 Flash/Pro** — Google Scholar supplement
- **GPT 5.4** — final output review (1M context, stable)

## Current Scope

Implemented:
- Bounded OpenCode runtime bridge and lifecycle surface
- File-intake safety and environment-aware pre-execution blocking
- Config-backed pipeline loading and validation
- Orchestrator baseline with intent classification and pipeline planning
- Control plane UI (React + Ant Design + ECharts)
- Local authentication and session management

Deferred:
- External skill repository auto-loading (bioSkills, ChemClaw, ClawBio)
- Autonomous research-boundary discovery
- Long-running checkpoint and resume
- Domain-specific tool adapters (Python, R, CLI, Docker, Conda)

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

Install and launch the UI:

```bash
python -m pip install -e .
abris-ui
```

Default launcher: enables OpenCode runtime, starts control plane on `127.0.0.1:18080`, default login `admin / abris-admin`.

Override:

```bash
abris-ui --host 127.0.0.1 --port 18081 --username admin --password abris-admin
```

## Project Layout

```text
src/abris/           # Python domain logic
configs/             # Pipeline and tool configurations
packages/            # TypeScript packages (opencode-bridge, control-plane-ui)
tests/               # Test suite
docs/                # Design documents
```

## License

GNU AGPL-3.0
