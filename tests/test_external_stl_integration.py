import importlib
import os
from pathlib import Path

import external_stl

def test_compose_query_includes_externalstl(monkeypatch):
    monkeypatch.setenv("MVP_EXTERNAL_STL_REL_PATH", "uploads/run123/Boat.stl")
    import rag.openai_file_search as ofs
    importlib.reload(ofs)
    importlib.reload(external_stl)
    spec = ofs._structured_query("generate geometry case")
    ctx = external_stl.get_external_stl_context()
    biased = ofs._apply_external_stl_bias(spec, ctx)
    query_text = ofs._compose_query_text(biased, "generate geometry case")
    assert "externalstl" in query_text.lower()


def test_metadata_filter_adds_externalstl(monkeypatch):
    monkeypatch.setenv("MVP_EXTERNAL_STL_REL_PATH", "uploads/run999/model.stl")
    import chains.rag_utils as rag_utils
    importlib.reload(rag_utils)
    importlib.reload(external_stl)
    filters = rag_utils.build_metadata_filter("tank with external geometry")
    assert filters.get("features") == "externalstl"


def test_generator_prompt_mentions_external_stl_instructions():
    prompt_text = Path("prompts/generator_system_prompt.md").read_text(encoding="utf-8")
    assert "External STL Handling" in prompt_text
    assert "External.stl" in prompt_text
