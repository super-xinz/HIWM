# Upstream provenance

HIWM Interaction Demo is a materially modified derivative project. A fresh repository history is used so its current development history is not confused with the upstream projects' contributor graph; this does not remove or replace upstream authorship.

## Base projects

| Component | Upstream | Base revision | License |
| --- | --- | --- | --- |
| Python service and modular media pipeline | [HumanAIGC-Engineering/OpenAvatarChat](https://github.com/HumanAIGC-Engineering/OpenAvatarChat) | release `0.6.0`, working-tree base `dcfba11` | Apache-2.0 |
| Vue/Electron Web UI | [HumanAIGC-Engineering/OpenAvatarChat-WebUI](https://github.com/HumanAIGC-Engineering/OpenAvatarChat-WebUI) | `a6182af` | Apache-2.0 |

The original repositories, their commit histories, and their contributor pages are the authoritative records of upstream contributions. Archived upstream documentation is retained under `docs/upstream/openavatarchat/` for reference and is excluded from the current documentation site.

## Material changes in this project

- Added the HIWM observation, three-candidate prediction, planning, durable-lock, execution, and next-turn feedback loop.
- Added consent, bounded client-perception, user-confirmed context, replay, ledger APIs, and deterministic safety validation.
- Added the macOS cloud-service profile, local supervisor, security regression tests, and documented research boundaries.
- Integrated the customized Web UI into one repository and moved it to the top-level `frontend/` project.
- Replaced upstream-facing README, repository metadata, documentation navigation, and release identity.

Compatibility identifiers such as `/openavatarchat/*`, selected configuration keys, and the `oac-bridge` channel ID may remain where changing them would break existing clients or stored browser data. Their presence is not a claim that this repository is an official OpenAvatarChat release.

## Upstream citation

When the underlying OpenAvatarChat work is used in research, cite the upstream project as requested by its authors:

```bibtex
@software{avatarchat2025,
  author = {Gang Cheng, Tao Chen, Feng Wang, Binchao Huang, Hui Xu, Guanqiao He, Yi Lu, Shengyin Tan},
  title = {OpenAvatarChat},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/HumanAIGC-Engineering/OpenAvatarChat}
}
```
