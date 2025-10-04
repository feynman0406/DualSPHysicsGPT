# S0 方案：vector_stores.search → 嚴格 JSON Schema（最小落地版）

目的
- 不使用 Responses 內建 file_search 工具（避免與嚴格 schema 衝突），直接利用 OpenAI Vector Store 的 search API 拉回候選片段。
- 將經過最小清洗與控長的引用片段（References）「整包」送往 Agent 2，使用嚴格 JSON Schema（response_format: json_schema, strict:true）生成最終結構化 JSON，再轉 XML。
- 最短路徑上線，觀測「嚴格 schema 合格率」與錯誤型態，為後續 S1/S2 升級提供依據。

整體流程

- Stage 1（檢索與清洗）
  - 使用 vector_stores.search 依 user_query 與 metadata_filter 拉回候選片段。
  - 本地做最小清洗：
    - 控長：每段 ≤ 400–600 字，總段數 8–12，總字數 5–8k。
    - 去重：移除重複或高度相似片段；同一 filename 的片段數量設上限（如 ≤ 3）。
    - 多樣性：優先選取來自不同檔案的片段。
    - 欄位關聯加權：命中 schema 欄位關鍵詞的片段權重提高（例如 2D/3D、timestep、dp、DBC/mDBC、邊界/幾何等）。
  - 必填覆蓋度預檢（本地邏輯）：
    - 粗略檢查 References 是否涵蓋 schema 的關鍵/必填欄位訊號。
    - 覆蓋度不足時採退避策略（見「失敗與退避」）。

- Stage 2（嚴格結構化）
  - 使用 Chat Completions + response_format: json_schema（strict:true），只輸出符合 schemas/dualsphysics_config_schema.json 的 JSON。
  - 嚴禁輸出任何非 JSON 文本與多餘鍵；後端再做一次 JSON Schema 驗證（雙保險）。
  - 正常情況下，將 JSON 傳入 normalize_case_config → generate_case_xml 生成 XML；嚴格模式預設不允許 XML fallback。

與現有程式碼的對接

- rag/openai_file_search.py
  - 新增或重用一個輔助函式 search_snippets（若不想改檔，亦可直接在 chains/generator.py 調用 client.vector_stores.search 並在當地做清洗）：
    - 輸入：vector_store_ids: List[str], query_text: str, metadata_filter: Dict[str,Any]|None, k: int = 8..12, char_limit: int = 400..600
    - 輸出：snippets: List[dict]（每項至少 { text, filename, file_id?, score }），並可回傳 applied_filter、嘗試紀錄、sources 摘要（便於 logs）
    - 內部策略：多組 metadata_filter 嘗試（含 None），合併後去重與重排序（可用簡易 MMR：score = α·sim − (1−α)·redundancy）；同檔片段上限

- chains/rag_utils.py
  - 新增 assemble_references(snippets, max_total_chars=8000) → str：將片段整理為 References 純文字區塊（每段前加 [filename] 標籤），同時保證總長度限制。
  - 新增 persist_sources(role, sources) 或重用既有 persist_sources 記錄 logs/last_run/generator_sources.json（引用清單）

- chains/generator.py
  - 新增旗標分支：USE_TWO_STAGE_RAG_SCHEMA=1 且 USE_RAG_PLANNING_AGENT=0 時，走 S0 路線：
    1) Stage 1：vector_stores.search → 清洗後的 snippets → ctx = assemble_references(snippets)
    2) Stage 2：schema = _load_json_schema()；llm_call(..., json_schema=schema, strict=True, temperature=0)
       - Human Prompt 裝載 [User Requirements] + [References]（見下）
    3) 後處理：JSON → normalize_case_config → generate_case_xml；禁止（或依旗標）XML fallback
    4) 持久化：persist_sources('generator', sources)

- llm/client.py
  - 現有 Structured Outputs 路徑已存在（json_schema != None 且未走 file_search 分支時，使用 Chat Completions 的 response_format: json_schema）
  - 若要使用 gpt-5 的嚴格輸出，視 API 支援情況擴充 _supports_structured_outputs 或改走 Responses 的 Structured Outputs（SDK 支援時）

Agent 2 Prompt 範例（簡版骨架）

System
- 你是一個結構化配置生成器。你的唯一輸出必須是符合給定 JSON Schema 的 JSON 物件，不得包含多餘鍵或任何非 JSON 文本。若必要欄位缺失，按 [Missing Policy] 處理，確保維度/單位一致性。

Human
- [Task]
  根據使用者需求（[User Requirements]）與引用片段（[References]），生成符合指定 JSON Schema 的配置 JSON。僅輸出 JSON 物件本體。
- [Constraints]
  - 嚴格遵守提供的 JSON Schema（additionalProperties: false、required 等）。
  - 僅使用 [References] 中可支持的資訊；不得杜撰來源未提及的數值。
- [Missing Policy]
  - 方案 A（預設）：若必填缺失，使用保守預設並保持整體一致性；不可引入不合理的數值。
  - 方案 B（嚴格）：若必填缺失則回傳錯誤（由後端判斷是否採用）。
- [User Requirements]
  {user_query}
- [References]
  {ctx}  # 片段控長＋去重，格式如：
         # [CaseWaveTank_Def.json] 引用文字...
         # [CaseSloshingHR_Def.json] 引用文字...

關鍵參數與建議

- 片段配額（建議值）：
  - k：8–12 段
  - 每段上限：400–600 字
  - 總字數：5–8k
  - 多樣性：每個 filename 至多 3 段，優先跨檔案
  - MMR 權重 α：~0.7（可視情調整）
- 欄位關聯關鍵詞（示意）：
  - 維度：["2D", "2-D", "two-dimensional", "3D", "3-D", "three-dimensional"]
  - 計算核心：["timestep", "dt", "dp", "density", "viscosity"]
  - 邊界與幾何：["boundary", "DBC", "mDBC", "wavemaker", "piston", "flap", "tank", "inlet", "outlet"]
  - 單位與一致性：["m/s", "s", "m", "kg/m^3", "Pa·s"]
- 覆蓋度預檢（示意）：
  - 基於 schema 的 required 清單與關鍵詞映射，統計 References 是否包含對應訊號。
  - 覆蓋不足時選擇「保守預設」或「報錯中止」（可由環境變數控制策略）。

失敗與退避策略

- 覆蓋度不足（Stage 1）：
  - 退避 1：補入你定義的 domain 預設（例如 dp/dt 的安全值），並在 System/Human 提示中強調「使用保守預設」。
  - 退避 2：直接中止，回傳缺失報告與建議補料清單，避免浪費 Agent 2 請求。
- 嚴格 schema 失敗（Stage 2）：
  - 於 logs/last_run/ 保存 References 與模型原始輸出，對失敗樣本集中觀測，調整片段權重與缺失策略。

環境變數（建議）

- USE_TWO_STAGE_RAG_SCHEMA=1
  - 開啟兩階段模式（generator_chain 入口優先）
- USE_RAG_PLANNING_AGENT=0
  - 關閉規劃 Agent，走 S0 直接 References 路（後續可升級）
- OPENAI_RAG_VS_DESIGN_ID
  - 指定 Vector Store ID
- DSPH_USE_JSON_SCHEMA=1、DSPH_STRICT_JSON_SCHEMA=1
  - 開啟嚴格 JSON Schema 輸出
- DSPH_FORBID_XML_FALLBACK=1
  - 禁止 XML fallback（建議）
- DSPH_DEBUG=1
  - 輸出除錯與 metrics、持久化 last_run

最小落地步驟（實作順序）

1) Stage 1 檢索與清洗
   - 新增 search_snippets（或直接在 generator 實作）：多組 metadata_filter 嘗試 → 合併 → 去重/控長/多樣性/關聯加權 → 得到 snippets
   - assemble_references(snippets) → ctx
   - persist_sources('generator', sources)

2) Stage 2 嚴格結構化
   - schema = _load_json_schema()
   - out = llm_call(messages, model, json_schema=schema, strict=True, temperature=0)
   - 驗證 JSON 並轉 XML（normalize_case_config → generate_case_xml）

3) 測試與觀測
   - 單元測試：組件化清洗與覆蓋度預檢
   - e2e 試跑三到五個代表案例（2D/3D、dam break、wavemaker、sloshing）
   - 保存失敗樣本的 References 與原始輸出，分析錯誤型態

與後續升級的關係

- S1：在 Stage 1 增加本地欄位抽取器（regex/小解析器），把 snippets 映射為半結構化的 extracted_params，提供給 Agent 2。可顯著提升合格率與一致性。
- S2：導入 RAG + Planning Agent（或工具嚴格化的 function.emit_plan），輸出 Plan JSON（包含 schema_guidance），讓 Agent 2 更容易一次通過。適合在 S0/S1 觀測後再投資。

附錄：Human Prompt 模板（可直接套用）

[Task]
根據使用者需求與引用片段（References），生成符合指定 JSON Schema 的 DualSPHysics 組態 JSON。僅輸出 JSON 物件本體。

[Constraints]
- 嚴格遵守提供的 JSON Schema（不得包含多餘鍵或任何非 JSON 文本）。
- 僅使用 References 中可支持的資訊；不得杜撰。
- 若遇到不一致或缺失，遵循 [Missing Policy]。

[Missing Policy]
- A（預設）：對缺失欄位採保守預設，並保持單位/維度一致性。
- B（嚴格）：若缺失則回傳錯誤（由後端控制是否啟用）。

[User Requirements]
{user_query}

[References]
{ctx}

驗收指標（初版）

- 嚴格 JSON Schema 合格率（一次通過/需修正/失敗）
- 失敗樣本的缺失/噪音型態（是否與片段控長、關聯加權或覆蓋度預檢有關）
- 平均延時與成本
- 審計資料（logs/last_run）：是否能足夠重現
