# Contributing

Thanks for improving HIWM Interaction Demo. This repository contains a Python service and a Vue/Electron client; changes that alter their shared contracts should update both sides and include regression coverage.

## Before opening a change

1. Create a focused branch and keep generated files, credentials, logs, ledgers, model weights, and real conversation data out of commits.
2. Initialize pinned third-party code with `git submodule update --init --recursive`; do not rewrite third-party history or remove its license files.
3. Preserve compatibility API and storage identifiers unless the change includes an explicit migration path.
4. Describe scientific and safety claims precisely. Do not introduce hidden-emotion, personality, deception, diagnosis, protected-trait, or high-impact suitability inference.

## Checks

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src scripts tests
bash -n scripts/setup_macos.sh scripts/start_macos.sh

cd frontend
pnpm install --frozen-lockfile
pnpm run check
pnpm run build

cd ../docs
npm ci
npm run docs:build
```

Keep pull requests small enough to review. Explain the behavior change, tests performed, privacy or cost impact, and any manual device checks still required. Upstream contributions are credited in `UPSTREAM.md`; current repository contributors are represented by this repository's own commit history.
