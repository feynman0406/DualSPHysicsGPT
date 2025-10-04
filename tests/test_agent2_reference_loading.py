import sys
import types

dotenv_stub = types.SimpleNamespace(load_dotenv=lambda: None)
sys.modules.setdefault("dotenv", dotenv_stub)

from scripts.mvp_direct_file_search import (
    REPO_ROOT,
    _prepare_reference_documents,
    _resolve_reference_path,
)


def _sample_agent1_output():
    return {
        "references": [
            {
                "filename": "CaseDambreak2D_Def.json",
                "attributes": {"source_path": "CaseDambreak2D_Def.json"},
            },
            {
                "filename": "CaseDamBreak3D_mDBC_Def.json",
                "attributes": {"source_path": "CaseDamBreak3D_mDBC_Def.json"},
            },
        ],
        "reference_rerank": {"indices": [1, 0]},
    }


def test_prepare_reference_documents_loads_top_file_only():
    docs = _prepare_reference_documents(_sample_agent1_output(), max_files=1, max_chars=50000)
    assert len(docs) == 1
    assert docs[0]["filename"] == "CaseDambreak2D_Def.json"
    assert docs[0]["full_text"].lstrip().startswith("{")
    assert isinstance(docs[0]["truncated"], bool)


def test_prepare_reference_documents_truncates_excerpt():
    docs = _prepare_reference_documents(_sample_agent1_output(), max_files=1, max_chars=10)
    assert len(docs) == 1
    assert docs[0]["truncated"] is True
    assert len(docs[0]["prompt_excerpt"]) == 10


def test_resolve_reference_path_uses_config_library():
    path = _resolve_reference_path('CaseDambreak2D_Def.json')
    assert path is not None
    expected = REPO_ROOT / 'AutoXml_script' / 'config_library' / 'CaseDambreak2D_Def.json'
    assert path.samefile(expected)

