from __future__ import annotations

from pathlib import Path
from typing import Callable

ROOT = Path('ui/app/src')


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='cp1252')


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.replace('\r\n', '\n'), encoding='utf-8')


def _fix_run_metadata(text: str) -> str:
    text = text.replace(
        "Started {formatRelativeTime(run.startedAt)} ¡P Duration",
        "Started {formatRelativeTime(run.startedAt)} | Duration",
    )
    text = text.replace(
        "{stlSize ?  : null}",
        "{stlSize ?  : null}",
    )
    return text


def _fix_run_card(text: str) -> str:
    replacements = {
        "return '?';": "return 'OK';",
        "return '�K';": "return 'RUN';",
        "return '!';": "return '!';",  # keep explicit
        "return '�E';": "return '--';",
        "?? '�X'": "?? 'N/A'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("return '--';", "return '--';")
    return text


def _fix_new_run_dialog(text: str) -> str:
    text = text.replace('��', 'X')
    text = text.replace('¡Ñ', 'X')
    text = text.replace('Triggering�K', 'Triggering...')
    return text


def _fix_artifact_viewer(text: str) -> str:
    text = text.replace('�P', ' | ')
    text = text.replace('Loading artifacts�K', 'Loading artifacts...')
    text = text.replace('Loading preview�K', 'Loading preview...')
    return text


def _fix_log_viewer(text: str) -> str:
    text = text.replace('—', '--')
    text = text.replace('…', '...')
    return text


def _fix_stage_progress(text: str) -> str:
    text = text.replace('·', ' | ')
    text = text.replace('—', '--')
    return text


def _fix_run_list_page(text: str) -> str:
    text = text.replace('Refreshing…', 'Refreshing...')
    text = text.replace('Tracking {activeRuns.length} active run{activeRuns.length > 1 ? '', 'Tracking {activeRuns.length} active run{activeRuns.length > 1 ? ')
    text = text.replace("'s' : ''}…", "'s' : ''}...")
    return text


def _fix_metrics_panel(text: str) -> str:
    text = text.replace('—', '--')
    text = text.replace('·', ' | ')
    text = text.replace('…', '...')
    return text


def _fix_overview_panel(text: str) -> str:
    text = text.replace('—', '--')
    text = text.replace('·', ' | ')
    text = text.replace('→', '->')
    return text


def _fix_utils_time(text: str) -> str:
    return text.replace('—', '--')


def _fix_utils_files(text: str) -> str:
    return text.replace('—', '--')


FIXERS: dict[Path, Callable[[str], str]] = {
    Path('components/RunMetadata.tsx'): _fix_run_metadata,
    Path('components/RunCard.tsx'): _fix_run_card,
    Path('components/NewRunDialog.tsx'): _fix_new_run_dialog,
    Path('components/ArtifactViewer.tsx'): _fix_artifact_viewer,
    Path('components/LogViewer.tsx'): _fix_log_viewer,
    Path('components/StageProgress.tsx'): _fix_stage_progress,
    Path('pages/RunListPage.tsx'): _fix_run_list_page,
    Path('components/MetricsPanel.tsx'): _fix_metrics_panel,
    Path('components/OverviewPanel.tsx'): _fix_overview_panel,
    Path('utils/time.ts'): _fix_utils_time,
    Path('utils/files.ts'): _fix_utils_files,
}

for rel_path, fixer in FIXERS.items():
    path = ROOT / rel_path
    original = _read_text(path)
    updated = fixer(original)
    if updated != original:
        _write_text(path, updated)
