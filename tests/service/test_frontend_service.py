from pathlib import Path

from service.frontend_service.frontend_service import (
    FrontendRegistrationOptions,
    _resolve_frontend_path,
)


def test_frontend_path_uses_top_level_project(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "service.frontend_service.frontend_service.DirectoryInfo.get_project_dir",
        lambda: str(tmp_path),
    )

    expected = Path(tmp_path) / "frontend/dist"
    assert _resolve_frontend_path(FrontendRegistrationOptions()) == expected


def test_frontend_path_can_be_overridden(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "service.frontend_service.frontend_service.DirectoryInfo.get_project_dir",
        lambda: str(tmp_path),
    )

    options = FrontendRegistrationOptions(
        frontend_dist_relative_path="custom/client-dist"
    )
    assert _resolve_frontend_path(options) == Path(tmp_path) / "custom/client-dist"


def test_frontend_defaults_to_hiwm_api_with_legacy_read_compatibility():
    options = FrontendRegistrationOptions()

    assert options.init_config_route == "/api/v1/runtime/config"
    assert options.legacy_init_config_routes == (
        "/openavatarchat/initconfig",
    )
