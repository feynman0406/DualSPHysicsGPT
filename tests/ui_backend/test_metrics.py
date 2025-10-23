from __future__ import annotations

from typing import Any

from ui_backend import metrics


def test_collect_resource_snapshot_without_psutil(monkeypatch):
    monkeypatch.setattr(metrics, "psutil", None)
    monkeypatch.setattr(metrics.shutil, "which", lambda _name: None)

    snapshot = metrics.collect_resource_snapshot()

    assert snapshot.cpu_percent is None
    assert any("psutil" in note for note in snapshot.notes)
    assert any("nvidia-smi" in note for note in snapshot.notes)


def test_collect_resource_snapshot_without_nvidia(monkeypatch):
    class _VirtualMemory:
        percent = 33.0
        used = 2 * 1024 * 1024
        total = 4 * 1024 * 1024

    class _PsutilStub:
        def cpu_percent(self, interval: Any = None) -> float:
            return 17.5

        def virtual_memory(self) -> _VirtualMemory:
            return _VirtualMemory()

    monkeypatch.setattr(metrics, "psutil", _PsutilStub())
    monkeypatch.setattr(metrics.shutil, "which", lambda _name: None)

    snapshot = metrics.collect_resource_snapshot()

    assert snapshot.cpu_percent == 17.5
    assert snapshot.memory_percent == 33.0
    assert snapshot.memory_used_mb == 2.0
    assert snapshot.memory_total_mb == 4.0
    assert snapshot.gpu == []
    assert any("nvidia-smi" in note for note in snapshot.notes)
