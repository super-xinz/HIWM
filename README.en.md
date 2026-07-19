# HIWM Interaction Engine

**A consent-first interaction-decision demo for the Human Interaction World Model (HIWM) concept.**

[中文](README.md) · [Architecture](docs/guides/project-architecture.zh-CN.md) · [Runtime](docs/guides/hiwm-runtime.md) · [API v1](docs/guides/api-v1.md) · [0.2.0 acceptance](docs/reports/acceptance-2026-07-19-v0.2.zh-CN.md)

The project combines real-time audio/video, speech recognition, structured interaction prediction, speech synthesis, and optional avatar pipelines. For each finalized user turn it freezes bounded, cited observations, asks for exactly three candidate communication actions, scores goal progress, expected information gain, risk, and uncertainty, durably locks the selected prediction before execution, and evaluates it against the next real response.

> [!IMPORTANT]
> This is an application-level research demo, not an independently trained or downloadable HIWM foundation model. Its probabilities are uncalibrated model estimates. It must not be used to infer hidden emotion, personality, deception, mental health, protected traits, or suitability for high-impact decisions.

## Repository layout

| Project | Location | Responsibility |
| --- | --- | --- |
| Python service | repository root and `src/` | WebRTC, ASR, HIWM planning, prediction ledger, TTS, session APIs |
| Vue/Electron client | `frontend/` | consent flow, media controls, derived evidence, three-branch decisions, event replay |

The customized frontend is vendored into this repository so a normal commit contains both projects. Third-party algorithms remain pinned Git submodules.

Since `0.2.0`, public integrations use the HIWM-owned `/api/v1` namespace and `hiwm.*` browser-storage keys. Legacy endpoints and stored data have compatibility migration. A read-only robot adapter exposes idempotent speech commands derived only from verified prediction-ledger records; arbitrary physical motion is intentionally out of scope.

## Quick start on macOS

```bash
git submodule update --init --recursive
bash scripts/setup_macos.sh
```

Then start the local service:

```bash
bash scripts/start_macos.sh
```

Open <http://127.0.0.1:8283>, enter the Alibaba Cloud Model Studio / DashScope key on the combined setup screen, and use the single consent-and-start action. The key is kept only in the current local service process and is not written to `.env` or browser storage; enter it again after restarting the service. An owner-only `.env` remains an optional unattended-startup fallback.

## Verification

```bash
.venv/bin/python -m pytest -q

cd frontend
pnpm install --frozen-lockfile
pnpm run check
pnpm run build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes. Never commit credentials, model weights, logs, ledgers, generated bundles, or real conversation data.

## Status and provenance

Version `0.2.0` is a research prototype. The hardened cloud HIWM path has not yet been re-run as a paid end-to-end validation, and real camera/microphone/speaker behavior still requires a consenting device test.

This project is materially modified from [OpenAvatarChat](https://github.com/HumanAIGC-Engineering/OpenAvatarChat) `0.6.0` at `dcfba11` and [OpenAvatarChat-WebUI](https://github.com/HumanAIGC-Engineering/OpenAvatarChat-WebUI) at `a6182af`. It is not an official upstream release. See [UPSTREAM.md](UPSTREAM.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and the [Apache-2.0 license](LICENSE).
