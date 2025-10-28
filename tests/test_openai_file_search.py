import importlib
from types import SimpleNamespace

import pytest


def test_response_with_file_search_uses_include_and_snippets(monkeypatch: pytest.MonkeyPatch) -> None:
    import rag.openai_file_search as ofs

    ofs = importlib.reload(ofs)

    call_results = [
        SimpleNamespace(
            file_id="file-1",
            filename="CaseA.json",
            score=0.9,
            attributes={"source_path": "CaseA.json"},
            text="  snippet A  ",
        ),
        SimpleNamespace(
            file_id="file-1",
            filename=None,
            score=None,
            attributes={"sha256": "abc123"},
            text="snippet B",
        ),
    ]

    class DummyToolCall:
        def __init__(self, results):
            self.id = "fs-call-123"
            self.status = "completed"
            self.queries = [{"text": "query"}]
            self.results = results

    monkeypatch.setattr(ofs, "ResponseFileSearchToolCall", DummyToolCall)

    class DummyResponse:
        def __init__(self) -> None:
            self.output = [DummyToolCall(call_results)]
            self.output_text = "analysis text"

    captured_kwargs: dict[str, object] = {}

    class DummyResponsesAPI:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return DummyResponse()

    class DummyClient:
        def __init__(self) -> None:
            self.responses = DummyResponsesAPI()

    monkeypatch.setattr(ofs, "_client", lambda: DummyClient())
    monkeypatch.setattr(ofs, "_persist_last_run", lambda info: None)
    ofs.clear_last_run_info()

    text = ofs.response_with_file_search(
        messages=[{"role": "user", "content": "generate dambreak"}],
        model="gpt-test",
        vector_store_ids=["vs-1"],
        metadata_filter={"case_type": "dambreak"},
    )

    assert text == "analysis text"
    assert captured_kwargs["include"] == ["file_search_call.results"]

    info = ofs.get_last_run_info()
    assert info is not None
    sources = info["sources"]
    assert len(sources) == 1
    source = sources[0]
    assert source["file_id"] == "file-1"
    assert source["filename"] == "CaseA.json"
    assert source["score"] == 0.9
    assert source["snippets"] == ["snippet A", "snippet B"]
    assert source["metadata"]["source_path"] == "CaseA.json"
    assert source["metadata"]["sha256"] == "abc123"
    assert source["search_call_id"] == "fs-call-123"


def test_agent1_sanitizes_snippet_sources(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import scripts.mvp_direct_file_search as mvp

    mvp = importlib.reload(mvp)

    sample_sources = [
        {
            "file_id": "file-1",
            "filename": "CaseA.json",
            "score": 0.88,
            "snippets": ["primary snippet"],
            "metadata": {"source_path": "CaseA.json"},
            "search_call_id": "fs-123",
        },
        {
            "file_id": "file-2",
            "filename": "CaseB.json",
            "score": 0.52,
            "snippets": [],
            "metadata": {"source_path": "CaseB.json"},
            "search_call_id": "fs-456",
        },
    ]

    import rag.openai_file_search as ofs
    ofs = importlib.reload(ofs)
    monkeypatch.setattr(ofs, "response_with_file_search", lambda *args, **kwargs: "analysis text")
    monkeypatch.setattr(ofs, "get_last_run_info", lambda: {"sources": sample_sources})
    monkeypatch.chdir(tmp_path)

    result = mvp.agent_1_file_search("generate geometry", "vs-1")

    assert result["references"][0]["snippets"] == ["primary snippet"]
    assert result["references"][0]["metadata"]["source_path"] == "CaseA.json"
    assert result["references"][0]["search_call_id"] == "fs-123"
    assert result["references"][1]["snippets"] == []
