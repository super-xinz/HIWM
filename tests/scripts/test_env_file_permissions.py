from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("script_name", ["setup_macos.sh", "start_macos.sh"])
def test_macos_script_creates_and_tightens_env_as_owner_only(script_name: str) -> None:
    script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")

    umask_index = script.index("umask 077")
    copy_index = script.index("cp .env.example .env")
    chmod_index = script.index("chmod 600 .env")

    assert umask_index < copy_index < chmod_index
    assert script.count("chmod 600 .env") == 1


@pytest.mark.parametrize("preexisting", [False, True])
def test_start_script_enforces_env_mode_at_runtime(tmp_path: Path, preexisting: bool) -> None:
    scripts_dir = tmp_path / "scripts"
    python_path = tmp_path / ".venv" / "bin" / "python"
    scripts_dir.mkdir(parents=True)
    python_path.parent.mkdir(parents=True)

    start_script = scripts_dir / "start_macos.sh"
    start_script.write_text(
        (ROOT / "scripts" / "start_macos.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text("DASHSCOPE_API_KEY=synthetic-test-key\n", encoding="utf-8")
    python_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python_path.chmod(0o700)

    env_path = tmp_path / ".env"
    if preexisting:
        env_path.write_text("DASHSCOPE_API_KEY=synthetic-existing-key\n", encoding="utf-8")
        env_path.chmod(0o644)

    subprocess.run(["/bin/bash", str(start_script)], cwd=tmp_path, check=True)

    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
