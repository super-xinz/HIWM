# HIWM Interaction Web

Vue 3 + TypeScript + Vite/Electron client for HIWM Interaction Engine. It is maintained in the same repository as the Python service and is served from `frontend/dist/` at `/ui` after a production build.

## Responsibilities

- informed-consent gate and media lifecycle controls;
- WebRTC/WebSocket communication with the Python service;
- bounded face-landmark, head-pose, waveform, pitch, energy, and pause derivation;
- user-confirmed session context and working-profile views;
- exactly three predicted action branches, selected-action explanation, and derived-event replay;
- session and runtime manager views.

Raw audio, video, images, and full landmark arrays are not written to the replay store by default. New clients use `/api/v1` and `hiwm.*` storage keys. Pre-0.2 endpoint aliases remain available, while old browser keys are migrated once so upgrades do not silently discard existing sessions.

## Development

From this directory:

```bash
pnpm install --frozen-lockfile
pnpm run dev
```

For a separate development server, create an ignored `.env` only when an explicit backend address is needed:

```dotenv
VITE_SERVER_IP=127.0.0.1
VITE_SERVER_PORT=8283
VITE_USE_SSL=false
```

With no variables, the browser client uses the current page origin.

## Checks and build

```bash
pnpm run check
pnpm run build
```

`dist/`, `dist-electron/`, `node_modules/`, and TypeScript build-info files are generated locally and intentionally excluded from Git. The Python service serves `frontend/dist/`; the root macOS setup script builds it automatically, and the Docker image builds it in a dedicated Node stage.

Electron development and packaging remain available through `pnpm run electron:dev` and the `build:*` scripts. Release signing, notarization, and update publishing are intentionally not configured; do not distribute unsigned desktop artifacts as trusted releases.

## Provenance

This client is materially modified from [OpenAvatarChat-WebUI](https://github.com/HumanAIGC-Engineering/OpenAvatarChat-WebUI) at base revision `a6182af`. It is not the official upstream WebUI. See the repository-root `UPSTREAM.md`, `THIRD_PARTY_NOTICES.md`, and `LICENSE`.
