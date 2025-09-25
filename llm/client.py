import os
import time
import json
import requests
from typing import List, Dict, Optional, Any

# ---- helpers ----
class LLMCallError(RuntimeError):
    pass



def _safe_to_dict(obj):
    try:
        return obj.to_dict()  # type: ignore[attr-defined]
    except Exception:
        try:
            return obj.model_dump()  # type: ignore[attr-defined]
        except Exception:
            return str(obj)


def _debug_print(label: str, payload) -> None:
    if os.environ.get('DSPH_DEBUG') != '1':
        return
    print(f"=== llm.debug: {label} ===")
    try:
        if isinstance(payload, str):
            print(payload)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"<failed to serialize debug payload: {exc}>")
        try:
            print(repr(payload))
        except Exception:
            pass
    print("=== llm.debug end ===")

def _extract_content_from_openrouter(resp_json: dict) -> str:
    """
    Extracts the main content from an OpenRouter response.
    - Tries to get choices[0].message.content first.
    - Then checks for choices[0].message["reasoning_content"] if the first is empty.
    - If tool_calls are present or content is still missing, it serializes the whole message.
    """
    try:
        choice = (resp_json.get("choices") or [])[0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        if content:
            return str(content).strip()
        # If content is empty, try to get reasoning_content
        rc = msg.get("reasoning_content")
        if rc:
            return str(rc).strip()
        # As a last resort, if all else fails, return the message object as a JSON string.
        return json.dumps(msg, ensure_ascii=False)
    except Exception as e:
        raise LLMCallError(f"OpenRouter response parse error: {e}; raw={resp_json}")


def _to_responses_input(messages: List[Dict[str, str]]):
    """Convert chat-style messages to the Responses API input format."""
    items = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        items.append(
            {
                "type": "message",
                "role": role,
                "content": [
                    {
                        "type": "input_text",
                        "text": str(content),
                    }
                ],
            }
        )
    return items

def _requests_post_json(url: str, headers: dict, payload: dict, timeout: float = 60.0, retries: int = 2):
    last_err = None
    for i in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code >= 200 and r.status_code < 300:
                return r
            # For 429/5xx errors, wait and then retry.
            if r.status_code in (429, 500, 502, 503, 504) and i < retries:
                time.sleep(1.5 * (i + 1))
                continue
            # For other errors, raise immediately without retrying.
            raise LLMCallError(f"HTTP {r.status_code}: {r.text}")
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            if i < retries:
                time.sleep(1.5 * (i + 1))
                continue
            raise LLMCallError(f"Request failed after retries: {e}") from e
    # This point should not be reached.
    raise LLMCallError(f"Request failed: {last_err}")

# ---- public API ----
def llm_call(
    messages: List[Dict[str, str]],
    model: str,
    reasoning: Optional[Dict[str, str]] = None,   # e.g. {"effort":"high"}
    temperature: Optional[float] = None,
    max_tokens: int = 20480 ,
    stop: Optional[List[str]] = None,
    file_search_vs_ids: Optional[List[str]] = None,
    metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> str:
    """
    Calls an LLM API, supporting both 'openai' and 'openrouter'.
    messages: [{"role":"system|user|assistant","content":"..."}]
    """
    if reasoning is None:
        reasoning = get_reasoning_config()
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        target_model = model or os.environ.get("OPENAI_MODEL_RESPONSES") or os.environ.get("OPENAI_MODEL", "gpt-4o")
        # 只有當模型是 reasoning model 時，才啟用 reasoning 功能
        final_reasoning = None
        if _is_reasoning_model(target_model):
            if reasoning is None:
                final_reasoning = get_reasoning_config()
            else:
                final_reasoning = reasoning

        is_reasoning_model = _is_reasoning_model(target_model)
        vector_store_ids = [vid for vid in (file_search_vs_ids or []) if vid]
        metadata_filter_clean: Optional[Dict[str, Any]] = None
        if metadata_filter:
            clean_filter = {k: v for k, v in metadata_filter.items() if v not in (None, "")}
            if clean_filter:
                metadata_filter_clean = clean_filter
        if vector_store_ids:
            try:
                from rag.openai_file_search import response_with_file_search
                temp_value = temperature if (temperature is not None and not is_reasoning_model) else None
                return response_with_file_search(
                    messages=messages,
                    model=target_model,
                    vector_store_ids=vector_store_ids,
                    metadata_filter=metadata_filter_clean,
                    max_output_tokens=max_tokens,
                    query_rewrite=True,
                    temperature=temp_value,
                    reasoning=final_reasoning,
                )
            except Exception as exc:
                raise LLMCallError(f"OpenAI File Search call failed: {exc}") from exc
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise LLMCallError("OPENAI_API_KEY environment variable not set")
        client = OpenAI(api_key=api_key)
        input_items = _to_responses_input(messages)

        kwargs = dict(
            model=target_model,
            input=input_items,
            max_output_tokens=max_tokens,
        )
        model_name = kwargs["model"]
        is_reasoning_model = _is_reasoning_model(model_name)
        debug_enabled = os.environ.get("DSPH_DEBUG") == "1"

        if (temperature is not None) and (not is_reasoning_model):
            kwargs["temperature"] = temperature

        if final_reasoning:
            kwargs["reasoning"] = final_reasoning

        def _call_chat_fallback(allow_reasoning: bool = True):
            legacy_kwargs = {
                "model": model_name,
                "messages": messages,
            }
            token_key = "max_completion_tokens" if is_reasoning_model else "max_tokens"
            legacy_kwargs[token_key] = max_tokens
            if (temperature is not None) and (not is_reasoning_model):
                legacy_kwargs["temperature"] = float(temperature)
            if allow_reasoning and reasoning:
                legacy_kwargs["reasoning"] = reasoning
            if stop:
                legacy_kwargs["stop"] = stop
            resp = client.chat.completions.create(**legacy_kwargs)
            if debug_enabled:
                _debug_print("openai.chat_completions.raw", _safe_to_dict(resp))
            return resp

        try:
            resp = client.responses.create(**kwargs)
            if debug_enabled:
                _debug_print("openai.responses.raw", _safe_to_dict(resp))
            text = (getattr(resp, "output_text", None) or "").strip()
            if text:
                if debug_enabled:
                    _debug_print("openai.responses.output_text", text)
                return text
            if debug_enabled:
                _debug_print("openai.responses.empty_output_text", _safe_to_dict(resp))
            fallback_resp = _call_chat_fallback()
            out_text = (fallback_resp.choices[0].message.content or "").strip()
            if debug_enabled:
                _debug_print("openai.chat_completions.output_text", out_text)
            return out_text
        except TypeError as e:
            if "reasoning" in str(e) and reasoning:
                kwargs.pop("reasoning", None)
                try:
                    resp = client.responses.create(**kwargs)
                    if debug_enabled:
                        _debug_print("openai.responses.retry_no_reasoning", _safe_to_dict(resp))
                    text = (getattr(resp, "output_text", None) or "").strip()
                    if text:
                        if debug_enabled:
                            _debug_print("openai.responses.output_text", text)
                        return text
                except TypeError:
                    pass
            try:
                fallback_resp = _call_chat_fallback()
            except TypeError as e2:
                if "reasoning" in str(e2) and reasoning:
                    fallback_resp = _call_chat_fallback(allow_reasoning=False)
                else:
                    raise LLMCallError(f"OpenAI chat.completions fallback failed: {e2}") from e2
            except Exception as e2:
                raise LLMCallError(f"OpenAI chat.completions fallback failed: {e2}") from e2
            out_text = (fallback_resp.choices[0].message.content or "").strip()
            if debug_enabled:
                _debug_print("openai.chat_completions.output_text", out_text)
            return out_text
        except AttributeError:
            try:
                fallback_resp = _call_chat_fallback()
            except TypeError as e2:
                if "reasoning" in str(e2) and reasoning:
                    fallback_resp = _call_chat_fallback(allow_reasoning=False)
                else:
                    raise LLMCallError(f"OpenAI chat.completions fallback failed: {e2}") from e2
            except Exception as e2:
                raise LLMCallError(f"OpenAI chat.completions fallback failed: {e2}") from e2
            out_text = (fallback_resp.choices[0].message.content or "").strip()
            if debug_enabled:
                _debug_print("openai.chat_completions.output_text", out_text)
            return out_text
        except Exception as e:
            if debug_enabled:
                _debug_print("openai.responses.exception", str(e))
            raise LLMCallError(f"OpenAI Responses call failed: {e}") from e
    elif provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise LLMCallError("OPENROUTER_API_KEY environment variable not set")

        base = os.environ.get("OPENROUTER_ENDPOINT", "https://openrouter.ai/api/v1").rstrip("/")
        model_name = os.environ.get("OPENROUTER_MODEL", model or "openai/gpt-4o-mini")

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # These headers help identify your app; OpenRouter uses them for tracking.
            "HTTP-Referer": os.environ.get("OPENROUTER_REFERRER", "http://localhost"),
            "X-Title": os.environ.get("OPENROUTER_SITE_NAME", "DualSPHysicsGPT"),
        }
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if (temperature is not None) and (not _is_reasoning_model(model_name)):
            payload["temperature"] = float(temperature)
        if reasoning:
            payload["reasoning"] = reasoning
        include_reasoning_flag = os.environ.get("OPENROUTER_INCLUDE_REASONING")
        if include_reasoning_flag:
            payload["include_reasoning"] = include_reasoning_flag.lower() in ("1", "true", "yes")
        if stop:
            payload["stop"] = stop

        try:
            r = _requests_post_json(f"{base}/chat/completions", headers, payload, timeout=90.0, retries=2)
            j = r.json()
            return _extract_content_from_openrouter(j)
        except Exception as e:
            raise LLMCallError(f"OpenRouter call failed: {e}") from e

    else:
        raise LLMCallError(f"Unsupported LLM_PROVIDER: {provider}")


def get_model_name() -> str:
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    if provider == "openrouter":
        return os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-r1:free")
    if provider == "openai":
        return os.environ.get("OPENAI_MODEL_RESPONSES") or os.environ.get("OPENAI_MODEL", "gpt-4o")
    raise LLMCallError(f"Unsupported LLM_PROVIDER: {provider}")


def get_reasoning_config() -> Optional[Dict[str, str]]:
    """Return reasoning config from env for the active provider, or None if unset."""
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        raw = os.environ.get("OPENAI_REASONING")
    elif provider == "openrouter":
        raw = os.environ.get("OPENROUTER_REASONING")
    else:
        raise LLMCallError(f"Unsupported LLM_PROVIDER: {provider}")

    if not raw:
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMCallError(f"Invalid reasoning JSON for provider '{provider}': {e}") from e

    if not isinstance(parsed, dict):
        raise LLMCallError("Reasoning configuration must be a JSON object")

    return parsed


def _is_reasoning_model(name: str) -> bool:
    n = (name or "").lower()
    # Is this a reasoning/thinking model?
    return any(tag in n for tag in ("gpt-5", "thinking", "o1", "o3", "o4"))




