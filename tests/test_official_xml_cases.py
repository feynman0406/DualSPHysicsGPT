"""Run official GenCase XML definitions to ensure they execute without errors."""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTOXML_DIR = ROOT / "AutoXml_script"

_EXCLUDE_FILES = {
    "case.xml",
    "GenCase_CaseTemplate.xml",
}

_EXCLUDE_PREFIXES = ("_FmtXML",)


def _collect_official_xmls() -> list[Path]:
    candidates = []
    for path in sorted(AUTOXML_DIR.glob("*.xml")):
        name = path.name
        if name in _EXCLUDE_FILES:
            continue
        if name.startswith(_EXCLUDE_PREFIXES):
            continue
        candidates.append(path)
    return candidates


OFFICIAL_XMLS = _collect_official_xmls()


def _resolve_gencase_exe() -> Path:
    env_bin_dir = os.environ.get("DSPH_BIN_DIR")
    if env_bin_dir:
        bin_dir = Path(env_bin_dir)
        if not bin_dir.is_absolute():
            bin_dir = (ROOT / bin_dir).resolve()
    else:
        bin_dir = (ROOT / "bin" / "windows").resolve()
    return bin_dir / "GenCase_win64.exe"


GENCASE_EXE = _resolve_gencase_exe()


@pytest.mark.slow
@pytest.mark.parametrize("xml_path", OFFICIAL_XMLS, ids=lambda p: p.stem)
def test_official_xml_runs_without_errors(xml_path: Path, tmp_path: Path) -> None:
    if platform.system().lower() != 'windows':
        pytest.skip('GenCase binary is Windows-only; skipping on non-Windows host.')
    if not GENCASE_EXE.exists():  # pragma: no cover - environment guard
        pytest.skip(f"GenCase binary not found at {GENCASE_EXE}")

    input_base = xml_path.with_suffix("")
    output_base = tmp_path / xml_path.stem
    cmd = [
        str(GENCASE_EXE),
        str(input_base),
        str(output_base),
        "-save:all",
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    assert proc.returncode == 0, (
        f"GenCase failed for {xml_path.name} (exit {proc.returncode}).\n"
        f"stdout:\n{stdout}\n----\nstderr:\n{stderr}"
    )
    assert "*** error" not in stdout.lower(), (
        f"GenCase reported an error for {xml_path.name}.\nstdout:\n{stdout}"
    )
    assert "*** error" not in stderr.lower(), (
        f"GenCase reported an error for {xml_path.name}.\nstderr:\n{stderr}"
    )
