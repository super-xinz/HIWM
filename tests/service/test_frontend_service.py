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
