# Changelog

All notable project-level changes are recorded here. Upstream OpenAvatarChat release history is archived under `docs/upstream/openavatarchat/`.

## 0.2.0 - 2026-07-19

- Unified runtime identity and version reporting under HIWM Interaction Engine.
- Added the stable `/api/v1` namespace with compatibility aliases for pre-0.2 clients.
- Migrated auth, timeline, and confirmed-profile browser data into `hiwm.*` keys without losing existing local sessions.
- Added a bounded, authenticated robot command feed derived only from verified prediction locks, with cursor and idempotency semantics.
- Added architecture, migration, API, robot-safety, and selective roadmap documentation.

## 0.1.0 - 2026-07-19

- Established HIWM Interaction Engine as an independent derivative project.
- Added the consent-first HIWM observation, three-branch prediction, planning, prediction-lock, execution, and feedback loop.
- Added bounded multimodal evidence, user-confirmed context, replay, ledger APIs, macOS setup, and safety regression tests.
- Integrated the customized Vue/Electron client as the top-level `frontend/` project.
- Replaced upstream repository identity and documented provenance, licensing, limitations, and verification.
