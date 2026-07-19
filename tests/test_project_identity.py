from __future__ import annotations

import json
import tomllib
from pathlib import Path

from project_identity import API_PREFIX, PROJECT_NAME, PROJECT_SLUG, PROJECT_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_public_project_versions_remain_aligned():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    frontend = json.loads(
        (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["name"] == "hiwm-interaction-engine"
    assert pyproject["project"]["version"] == PROJECT_VERSION
    assert frontend["version"] == PROJECT_VERSION


def test_public_identity_uses_hiwm_namespace():
    assert PROJECT_NAME == "HIWM Interaction Engine"
    assert PROJECT_SLUG == "hiwm"
    assert API_PREFIX == "/api/v1"
