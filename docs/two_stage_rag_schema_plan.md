# 兩階段 RAG → 嚴格 JSON Schema 實作計畫

目的
- 在不違反 OpenAI 平台「嚴格 JSON Schema 與內建工具（file_search）不可同請求共存」的前提下，提供穩定的兩階段流水線：
  1) Stage 1 檢索：以向量庫搜尋片段（不呼叫 Responses 工具、不啟用 file_search）
  2) Stage 2 結構化：以 response_format: json_schema（strict: true）產生符合 schemas/dualsphysics_config_schema.json 的 JSON，後續轉成 XML

- 保留現有單步路線（單步 file_search 或單步嚴格 Schema）不受影響；透過新旗標切換。

關鍵原則
- 分離檢索與結構化生成在不同 API 請求內完成。
- Stage 1 僅負責檢索與清洗片段（snippets）；Stage 2 僅負責嚴格結構化輸出。
- 引用與審計資料（sources、filter、query_spec）持久化在 logs/last_run 下，與最終 JSON Schema 輸出解耦。

---

整體架構與路線

現況（簡述）
- chains/generator.py 目前只做一次 llm_call：
  - 若 llm_kwargs 有 file_search_vs_ids → llm/client.py 會改走 rag/openai_file_search.response_with_file_search（Responses API + tools:file_search）
  - 若 llm_kwargs 有 json_schema（且未啟用 file_search 分支）→ 走 Chat Completions + response_format: json_schema（嚴格輸出）
  - 兩者互斥，無法同請求共存

目標（兩階段新管線）
- 新旗標 USE_TWO_STAGE_RAG_SCHEMA=1 啟用 two-stage 管線
- Stage 1：向量庫 API 檢索 snippets（不呼叫 Responses API，不啟用 file_search 工具）
- Stage 2：以 json_schema + strict 進行結構化輸出，後續 normalize_case_config → generate_case_xml

---

環境變數與行為對照

- USE_TWO_STAGE_RAG_SCHEMA=1
  - 啟用兩階段管線（優先於既有路線）
- OPENAI_RAG_VS_DESIGN_ID
  - 指定向量庫（vector store id）供 Stage 1 檢索
- DSPH_USE_JSON_SCHEMA=1
  - Stage 2 啟用嚴格輸出（此旗標最佳與兩階段並用）
- DSPH_STRICT_JSON_SCHEMA=1
  - Stage 2 設定 strict:true；若不符合 schema，直接報錯
- DSPH_FORBID_XML_FALLBACK=1
  - 兩階段建議預設禁止 XML fallback，確保結構化生成可靠
- DSPH_DEBUG=1
  - 輸出偵錯資訊（prompt metrics、持久化 last_run）

備註：若你打算使用 gpt-5 並且平台已支援 Structured Outputs，需更新 llm/client.py 的 _supports_structured_outputs（見後述）。

---

需新增/改動的檔案與函式

1) rag/openai_file_search.py（新增 Stage 1 純檢索 API）
- 新增：search_snippets
  ```python
  def search_snippets(
      vector_store_ids: List[str],
      query_text: str,
      metadata_filter: Optional[Dict[str, Any]] = None,
      k: int = 8,
      char_limit: int = 600,
      rewrite: bool = True,
  ) -> Dict[str, Any]:
      """
      不使用 Responses 工具；直接呼叫 client.vector_stores.search。
      回傳:
        {
          "snippets": [
            {"text": str, "file_id": str, "filename": str, "score": float, "attributes": dict}
          ],
          "applied_filter": { ... } | None,
          "attempts": [ ... ],  # 嘗試不同 filter 的紀錄（沿用 _select_filter_and_search）
          "sources": [ {file_id, filename, score, attributes} ... ]
        }
      """
  ```
- 新增：format_references
  ```python
  def format_references(snippets: List[Dict[str, Any]]) -> str:
      """
      以簡潔格式輸出引用片段，控制長度，避免 prompt 超長。
      例：
      [CaseWaveTank_Def.json] <摘錄內容...>
      [CaseSloshingHR_Def.json] <摘錄內容...>
      """
  ```
- 新增持久化（two_stage_search.json）
  ```text
  logs/last_run/two_stage_search.json  # 包含 query_spec、applied_filter、snippets 摘要
  ```
- 內部可重用現有的：
  - _structured_query / _compose_query_text（查詢重寫）
  - _build_filter_payload（過濾）
  - _select_filter_and_search（或抽取其邏輯）

2) chains/rag_utils.py（共用工具）
- 新增：assemble_rag_context
  ```python
  def assemble_rag_context(snippets: List[Dict[str, Any]], max_total_chars: int = 8000) -> str:
      """
      將 snippets 轉為 [References] 文字區塊；限制總長度（總字數、每段上限），並去重。
      """
  ```
- 新增：persist_two_stage_sources
  ```python
  def persist_two_stage_sources(role: str, sources: List[Dict[str, Any]]) -> None:
      """
      將 Stage 1 sources 保存於 logs/last_run/{role}_sources.json
      """
  ```

3) chains/generator.py（新增兩階段生成管線）
- 新增：generator_chain_two_stage
  ```python
  def generator_chain_two_stage(user_query: str, *, strict: bool = True) -> Dict[str, Any]:
      # Stage 1: 搜尋 snippets
      design_vs_id = os.environ.get("OPENAI_RAG_VS_DESIGN_ID")
      filters = build_metadata_filter(user_query)  # 既有方法
      search = search_snippets(
          vector_store_ids=[design_vs_id] if design_vs_id else [],
          query_text=user_query,
          metadata_filter=filters,
          k=8, char_limit=600, rewrite=True
      )
      ctx = assemble_rag_context(search["snippets"])

      # 準備訊息（System + Human）
      sys_prompt = _read(PROMPT_PATH)
      human_content = (
          "[Task] 根據使用者需求與 [References] 產生符合 JSON Schema 的 DualSPHysics 設定 JSON。\n"
          "[Constraints] 嚴格遵守 Schema，不輸出多餘鍵或文字。\n"
          f"[User Requirements]\n{user_query}\n[References]\n{ctx}\n"
      )
      lc_messages = [SystemMessage(content=sys_prompt), HumanMessage(content=human_content)]
      messages = _to_openai_messages(lc_messages)

      # Stage 2: 嚴格 JSON Schema
      schema = _load_json_schema()
      out_text = llm_call(messages, model=get_model_name(), reasoning=get_reasoning_config(),
                          json_schema=schema, strict=True, temperature=0)

      # 解析 JSON → 正規化 → 生成 XML（禁止 fallback）
      payload = json.loads(out_text)
      normalization = normalize_case_config(payload)
      xml = generate_case_xml(normalization.config)

      # sources 持久化（optional 回傳 Document-like）
      persist_two_stage_sources('generator', search["sources"])
      docs = [
          Document(page_content=s.get("text", ""), metadata={"source": (s.get("filename") or s.get("file_id") or "unknown")})
          for s in search["snippets"]
      ]
      return {"xml": xml, "config": normalization.config, "sources": docs}
  ```
- 在既有 generator_chain 開頭加入分支：
  ```python
  if os.environ.get("USE_TWO_STAGE_RAG_SCHEMA") == "1":
      return generator_chain_two_stage(user_query)
  ```

4) llm/client.py（必要時更新模型支援）
- 目前 _supports_structured_outputs 僅列 gpt-4o/mini：
  ```python
  def _supports_structured_outputs(model: str) -> bool:
      supported = ["gpt-4o", "gpt-4o-mini", "gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18"]
      return any(m in model.lower() for m in supported)
  ```
- 若要使用 gpt-5 的嚴格 schema，需擴充此判斷，或改以 try/except 探測特徵（建議先白名單加入 "gpt-5" 相關字樣，確保不誤拒）。

5) prompts/generator_system_prompt.md（小幅增補，兼容舊路徑）
- 追加兩階段模式適用段落（不破壞舊有行為）：
  - 僅依據 [References] 的內容生成，不得憑空杜撰。
  - 嚴格遵守 JSON Schema（additionalProperties: false / required），不得輸出註解、文字或多餘鍵。
  - 若片段間矛盾，以較晚且具體者為準，維持整體參數一致。

---

提示模板（Stage 2 Human 範例）

```
[Task]
根據使用者需求與 [References]，產生符合 JSON Schema 的 DualSPHysics 設定 JSON，且僅輸出 JSON 本體。

[Constraints]
- 嚴格遵守提供的 Schema：不得包含多餘鍵、不得包含註解或任何非 JSON 內容。
- 對缺失參數採保守預設，但需保持內部一致性（如維度/單位一致）。

[User Requirements]
{user_query}

[References]
{ctx}
```

---

測試計畫

新增 tests/test_two_stage_rag_schema.py
- test_two_stage_pipeline_happy_path
  - 設定 USE_TWO_STAGE_RAG_SCHEMA=1、DSPH_USE_JSON_SCHEMA=1、DSPH_STRICT_JSON_SCHEMA=1、OPENAI_RAG_VS_DESIGN_ID=xxx
  - mock search_snippets 回傳 3~8 段片段；mock llm_call 回傳合法 JSON
  - 驗證：normalize_case_config → generate_case_xml 成功，並持久化 logs/last_run 檔案存在
- test_two_stage_schema_violation
  - mock llm_call 回傳不符合 schema 或多餘鍵 → 應丟錯（不做 XML fallback）
- test_two_stage_no_matches
  - search_snippets 回空 → Stage 2 仍要求嚴格 JSON，允許回傳合理預設或報錯（依產品需求決定）
- test_flag_priority_two_stage（可放在 tests/test_rag_flags.py）
  - 若 USE_TWO_STAGE_RAG_SCHEMA=1，應優先走兩階段；不應走單步 file_search 或單步 schema

---

風險與對策

- 模型支援 Structured Outputs
  - 若選 gpt-5，需確認 API 支援度；否則先用 gpt-4o/mini，或擴充 _supports_structured_outputs
- 片段長度與重複
  - Stage 1 要嚴格控長與去重，避免 Stage 2 prompt 超長
- 引用與合規
  - citations 不混入 Schema JSON；另持久化 sources.json/two_stage_search.json，便於審計
- 收斂與可重現性
  - temperature=0，top_p=1；System Prompt 明確要求「僅輸出 JSON」

---

推進步驟（最小可行）

1) rag/openai_file_search.py：新增 search_snippets、format_references、two_stage_search.json 持久化
2) chains/rag_utils.py：新增 assemble_rag_context、persist_two_stage_sources
3) chains/generator.py：新增 generator_chain_two_stage；在 generator_chain 加 USE_TWO_STAGE_RAG_SCHEMA=1 分支
4) llm/client.py：必要時擴充 _supports_structured_outputs 支援目標模型
5) prompts/generator_system_prompt.md：增補兩階段限制段
6) 測試：新增 two-stage 單元測試與旗標優先測試
7) 文檔：本檔與 README / config.json 範例更新

---

附錄：與現有路線的關係

- 單步 file_search（Responses + tools:file_search）：保留，不變
- 單步嚴格 Schema（Chat Completions + response_format: json_schema）：保留，不變
- 兩階段（本計畫）：僅在 USE_TWO_STAGE_RAG_SCHEMA=1 時啟用，且在 chains/generator.py 優先攔截

---

驗收標準

- 在 USE_TWO_STAGE_RAG_SCHEMA=1 的情況下：
  - 看到 logs/last_run/two_stage_search.json 與 generator_sources.json（或相同命名）
  - generator 回傳的結果中，config 通過 normalize_case_config，成功生成 XML
  - 當 llm 輸出不符合 schema 時，流程會明確報錯（strict 模式禁止 fallback）
