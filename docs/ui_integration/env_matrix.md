# MVP Environment Matrix

## CLI Entry Points
- `python scripts/mvp_direct_file_search.py [--query TEXT] [--pause-after-agent1] [--execute]`
  - Canonical MVP invocation used for baseline capture; emits stdout/stderr to console and writes artifacts to `logs/mvp/`.
- `python docs/ui_integration/mvp_reference_runner.py [MVP_ARGS]`
  - Optional wrapper that configures UTF-8 output on Windows and mirrors the MVP stdout/stderr into `logs/mvp/reference_run/mvp_run.log` while copying artifacts to the reference directory.

## Environment Variables
| Variable | Required | Default | Source | Effect | Notes |
| --- | --- | --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes | ¡X | `.env` / shell | Authenticates OpenAI client for File Search and chat calls. | Script exits during environment check if unset. |
| `OPENAI_RAG_VS_DESIGN_ID` | Yes | ¡X | `.env` / shell | Vector store identifier queried by Agent 1. | Must correspond to an uploaded DualSPHysics design corpus; failure aborts Agent 1. |
| `OPENAI_MODEL` | No | `gpt-4o` | `.env` / shell | Model name passed to both agents. | Higher-tier models (e.g., `gpt-5`) can require matching `OPENAI_REASONING`. |
| `OPENAI_REASONING` | No | ¡X | `.env` / shell | JSON reasoning configuration forwarded with OpenAI requests. | Only honored when the selected model supports reasoning parameters. |
| `AGENT2_MAX_REFERENCE_FILES` | No | `1` | `.env` / shell | Cap on local reference JSON files provided to Agent 2. | Increase to inspect multiple exemplars; impacts prompt length. |
| `AGENT2_REFERENCE_MAX_CHARS` | No | `6000` | `.env` / shell | Max characters loaded from each reference. | Helps bound prompt size; truncate if hitting token limits. |
| `PYTHONIOENCODING` | Recommended (Windows) | ¡X | shell | Forces UTF-8 console output. | Prevents `UnicodeEncodeError` on CP950/Big5 consoles when agents print Unicode analysis. |
| `https_proxy` / `http_proxy` | Optional | ¡X | shell | Proxy settings honored by `httpx`. | Configure when outbound network requires proxying. |

Additional `.env` values (`LLM_PROVIDER`, `USE_RAG`, `OPENAI_MODEL_RESPONSES`, etc.) do not alter the standalone MVP run.
