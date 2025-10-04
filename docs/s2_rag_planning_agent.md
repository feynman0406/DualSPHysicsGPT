# S2 方案：RAG + Planning Agent → 嚴格 JSON Schema（進階可審計版）

目標
- Stage 1（Agent 1：RAG + Planning）：透過 OpenAI file_search 或 vector_stores.search 檢索，先完成「選材與規劃」，輸出可審計的 Plan JSON（包含引用片段與對 Schema Agent 的指導）。
- Stage 2（Agent 2：Schema）：根據 Plan JSON 的 evidence 與 schema_guidance，以 response_format: json_schema（strict:true）輸出完全符合 schemas/dualsphysics_config_schema.json 的 JSON，後續轉 XML。

為何需要 Planning Agent
- 避免把大量噪音片段直接丟給嚴格 schema，導致收斂困難或缺欄位。
- 讓「選材/抽取/缺失與衝突處理策略」在 Stage 1 就明確化，Stage 2 僅需「填表」，一次通過率↑、可觀測性↑。

平台限制與做法
- 同一請求內，response_format: json_schema（strict）不能與內建 file_search 共存。
- 兩個選項：
  1) 兩請求路線（較穩定）：
     - 先用 vector_stores.search 檢索與本地重排序/控長 → 匯整 Plan JSON（可透過一般 Chat 請求協助整理，非嚴格模式）。
     - 再以嚴格 schema 請求產出最終 JSON。
  2) 單請求工具化（進階）：
     - 在同一 Responses 請求中提供 tools:file_search 與「function.emit_plan（strict:true）」；模型先檢索，最後以「函式呼叫」輸出 Plan JSON。
     - 注意：這走「工具嚴格化」，不是 response_format 嚴格模式，因此不違反限制。

OpenAI File Search 設定（固定 top-k=3）
- 來源語料：`AutoXml_script/config_library/*.json`（完整案例，不切 chunk），向量庫 ID 來自 `rag/vector_stores.json` → `vs_68cc41440b9c8191bb5ef0fce9c4417f`。
- 單次檢索：Agent 1 僅允許呼叫 file_search 一次（`max_num_results=3`），禁用額外 retry；若結果不足改由後續流程補救。
- metadata_filter：沿用既有計畫中定義的 `chains/rag_utils.build_metadata_filter(query)`，預設從使用者 query 解析 case_type 與 dim。對當前 dambreak 規劃的預設值為：
  ```json
  {
    "case_type": "dambreak",
    "dim": "2D"
  }
  ```
  若需求提及「mDBC」或「3D」，允許在原有過濾器基礎上追加 `{"features": "mDBC"}` 或改寫 `dim: "3D"`；必要時可透過控制器覆寫 metadata_filter。無論是否覆寫，Plan JSON `metadata_filter` 必須回報實際使用值，並於 logs/last_run/metadata.json 落盤。
- 查詢文字：使用 `_structured_query` 產生 MUST/SHOULD/MUST_NOT，搭配 rewrite=true；若無命中，保留第一次查詢內容於 Plan JSON 的 `query` 欄位以利診斷。

Agent 1 引用評分與調整策略
- XML 解析來源：對每個檢索結果載入 `AutoXml_script/config_library` 中對應 JSON 或 XML。評分標準：每個維度採 1–5 分離散刻度（1=幾乎無法沿用，5=可直接套用），不加權，統計平均時可直接取算術平均。計算下列 4 維度：
  1. **Algorithm**（流程與主要指令是否可直接沿用）
  2. **Geometry**（幾何尺寸與填充是否貼近需求；若須修改，描述具體差異）
  3. **Boundary / Materials**（mk、邊界條件與浮體設定適配度）
  4. **Execution / Schedules**（execution.parameters、gauges、timeout 等）
- 在 `curated_examples[*].rationale` 中逐條說明「保留原因 + 必要調整」，格式建議：
  ```
  Algorithm=1, Geometry=0.5 → 算法可沿用，但需把幾何尺寸 X 改為 ...
  ```
  若需調整，明確指出「需修改點」例如「geometry.mainlist 第 2 段 drawbox 尺寸需改為 3.2 m」。
- `curated_examples[*].spans[*].quote` 儘量引用對應 XML/JSON 片段，quote 長度 < 400 字；同檔片段上限 3 段。

schema_guidance 待辦註記
- 目前由後續 Schema Guidance Agent 處理，Agent 1 僅需提供待填資訊與缺失描述。請在 `schema_guidance` 寫入占位符：
  ```
  <<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>
  ```
- 以結構化 TODO 模版彙整資訊，建議格式：
  ```
  <<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>
  [required_fields]
  - execution.parameters.StepAlgorithm → 需確認 semi-implicit 或 Verlet
  - wavepaddles.piston.children → 缺子節點，請參考 curated_examples[1]

  [assumptions]
  - 若無額外 boundary，維持 mkbound=0
  - geometry.lists.GeometryForNormals 沒命中則按 default 建立

  [open_questions]
  - geometry.mainlist 是否需要 layers vdp?
  - 是否需額外 gauges 觀測
  ```
  後續 Schema Guidance Agent 依 `required_fields`、`assumptions`、`open_questions` 三段內容結合 curated_examples 與 extracted_params 生成最終指引；若有額外需求可增列其他段落（如 `constraints`、`unit_checks`）。
- 若 Stage 2 失敗並觸發重試，Agent 1 需在 `schema_guidance` 新增 `retry_{n}` 區塊，摘要失敗訊息、已補強欄位與下一步行動，確保多輪迭代可審計。

單次檢索下的最佳流程建議
1. `build_metadata_filter(query)` → 得到初始 metadata_filter，並寫入 Plan JSON。
2. 呼叫 `response_with_file_search`（OpenAI Responses API + file_search），`max_num_results=3`，若無結果將 `curated_examples` 設為空陣列、於 `missing_params` 與 `schema_guidance` 清楚註記「檢索無匹配」，同時在 logs/last_run/planning_plan.json 留存 `no_results: true` 旗標。
3. 解析 3 筆內 XML/JSON，依上方評分規則整理 `curated_examples`、`extracted_params`、`missing_params`、`conflicts`。
4. 以 `coverage` 檢查 case_type / dim / features 覆蓋度，缺欄位寫入 `missing_params` 並在 `schema_guidance` 部分註記。
5. 將引用與分析寫入 Plan JSON，產出 `logs/last_run/planning_plan.json` 供 Agent 2 與審計使用。
6. 若 Stage 2（Schema Agent）回傳失敗，將錯誤訊息附帶給 Agent 1，重新啟動規劃流程：更新 `missing_params`/`conflicts`、調整評分與引用，並重新生成 Plan JSON（需記錄 retry 次數與原因）。

Plan JSON 資料契約（Agent 1 → Agent 2）
- 目的：承載「哪些檔、哪些片段、為何納入、缺失與衝突、如何填 schema」的規劃資訊。
- JSON Schema（建議版本；可依需求擴充）：
```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "query": { "type": "string", "maxLength": 4000 },
    "metadata_filter": {
      "type": ["object", "null"],
      "additionalProperties": { "type": "string" }
    },
    "curated_examples": {
      "type": "array",
      "maxItems": 12,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "file_id": { "type": ["string", "null"] },
          "filename": { "type": "string" },
          "rank": { "type": "integer", "minimum": 1 },
          "score": { "type": ["number", "null"] },
          "rationale": { "type": "string", "maxLength": 1000 },
          "spans": {
            "type": "array",
            "maxItems": 6,
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "start": { "type": ["integer", "null"] },
                "end": { "type": ["integer", "null"] },
                "quote": { "type": "string", "maxLength": 600 }
              },
              "required": ["quote"]
            }
          }
        },
        "required": ["filename", "rank", "spans"]
      }
    },
    "coverage": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "case_type": { "type": ["string", "null"] },
        "dim": { "type": ["string", "null"], "enum": ["2D", "3D", null] },
        "features": {
          "type": "array",
          "items": { "type": "string" },
          "maxItems": 16
        }
      }
    },
    "extracted_params": {
      "type": "array",
      "maxItems": 64,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "name": { "type": "string" },
          "value": { "type": ["string", "number", "boolean"] },
          "unit": { "type": ["string", "null"] },
          "source": { "type": "string" }
        },
        "required": ["name", "value", "source"]
      }
    },
    "missing_params": {
      "type": "array",
      "maxItems": 64,
      "items": { "type": "string" }
    },
    "conflicts": {
      "type": "array",
      "maxItems": 32,
      "items": { "type": "string" }
    },
    "schema_guidance": { "type": "string", "maxLength": 4000 },
    "citations": {
      "type": "array",
      "maxItems": 24,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "file_id": { "type": ["string", "null"] },
          "filename": { "type": "string" },
          "span_index": { "type": "integer" },
          "quote": { "type": "string", "maxLength": 600 }
        },
        "required": ["filename", "span_index", "quote"]
      }
    }
  },
  "required": ["query", "curated_examples", "schema_guidance"]
}
```

工具嚴格化（進階單請求）示意
- Responses API 請求（概念示例；實作時請依 SDK/版本調整）：
```json
{
  "model": "gpt-5.1",
  "input": "請根據需求先檢索文件，再產生 Plan JSON。",
  "tools": [
    { "type": "file_search" },
    {
      "type": "function",
      "function": {
        "name": "emit_plan",
        "description": "輸出選材與規劃的 Plan JSON。最後只呼叫一次。",
        "strict": true,
        "parameters": { /* 上述 Plan JSON Schema */ }
      }
    }
  ],
  "attachments": [
    { "vector_store_id": "vs_XXXXX", "tools": [{ "type": "file_search" }] }
  ],
  "tool_choice": { "type": "function", "function": { "name": "emit_plan" } },
  "temperature": 0
}
```
- 注意：
  - 這不是 response_format 嚴格模式；嚴格在「函式 arguments」層由工具 schema 約束。
  - 提示要明確：「先檢索→篩選→萃取→列缺失與衝突→最後只呼叫一次 emit_plan」。

Agent 提示骨架（落地時再精設）
- Agent 1（RAG + Planning）
  - System 要點：
    - 任務：選材與規劃，輸出 Plan JSON，禁止生成最終配置。
    - 僅依據檢索結果；對引用 quote 控長；列出缺失與衝突；`schema_guidance` 僅填入占位符與待辦說明，實際補寫交由後續 Agent。
    - 僅呼叫一次 emit_plan（若採工具嚴格化）；明確聲明單次 file_search 限制，若無結果需在 Plan JSON 標記 `missing_params`/`schema_guidance` 中的 fallback 策略。
  - Human 結構（兩請求時）：
    - [Task] 從候選片段中挑選具價值的檔案與片段，並規劃如何映射到指定 JSON Schema。
    - [User Requirements] 原始需求（裁切後）
    - [Candidates] 來自 vector_stores.search 的候選（控長 + 去重）
    - [Requirements] 控長規範、每檔片段上限、多樣性、關鍵欄位覆蓋、缺失/衝突列出、輸出 Plan JSON

- Agent 2（Schema）
  - System 要點：
    - 唯一輸出是符合指定 JSON Schema 的 JSON；不得包含多餘鍵與任何非 JSON 文本。
    - 僅使用 Plan JSON 的 evidence 與 schema_guidance；缺失處理依 guidance 策略。
  - Human 結構：
    - [Task] 依 Plan JSON 與 User Requirements 生成 JSON。
    - [Plan JSON] 上述結構
    - [Schema] schemas/dualsphysics_config_schema.json（或名稱）
    - [Constraints] 嚴格遵守 schema；禁止幻覺；單位與維度一致性。

整合點（程式碼）
- 新增：agents/planning_agent.py（或 rag/planning_agent.py）
  - run_planning_agent(query, vs_ids, metadata_filter, mode="two-requests"|"single-request") -> plan_json
    - two-requests：vector_stores.search + 本地重排序 → Chat 彙整 Plan JSON（或全本地生成）
    - single-request：Responses（file_search + function.emit_plan）
- chains/generator.py
  - 在 USE_TWO_STAGE_RAG_SCHEMA=1 且 USE_RAG_PLANNING_AGENT=1 時：
    - Stage 1：plan_json = run_planning_agent(...)
    - Stage 2：以 plan_json.schema_guidance 與 curated_examples.spans.quote 為主體組裝 Prompt，使用嚴格 JSON Schema 生成 JSON
- llm/client.py
  - 選用兩請求或單請求工具化時，提供對應封裝（例如 run_rag_planning_agent）
- chains/rag_utils.py
  - 可保留 assemble_references/persist_sources；若採 Plan JSON，sources 取自 curated_examples/citations

片段與長度策略（建議值）
- k（curated_examples.spans 總段數）：8–12
- 每段 quote 上限：400–600 字
- 每 filename 段數上限：≤ 3
- 多樣性：不同 filename 優先
- 欄位關聯關鍵詞加權：維度/邊界/幾何/時間步長/dp/單位
- 覆蓋度預檢：以 schema required 對照候選片段中的訊號命中率；不足時在 schema_guidance 指定處理策略（保守預設或放棄）

觀測與回滾
- logs/last_run/two_stage_search.json：檢索與重排序摘要。
- logs/last_run/planning_plan.json：Plan JSON（Agent 1 的輸出），需新增：
  - `status`: completed / no_results / retrying
  - `attempt`: 第幾次規劃
  - `plan_completion_rate`: 已完成欄位數 ÷ schema 必填欄位數（四捨五入至小數兩位）
  - `stage2_feedback`: 若 Stage 2 失敗，保存錯誤訊息與時間戳
- logs/last_run/generator_sources.json：最終使用的引用清單（供審計）。
- 監控與量測：
  - 每次 Plan JSON 產出後更新 `metrics/plan_runs.csv`（日期、query、status、completion_rate、stage2_passed、notes）。若 completion_rate < 0.7 或 stage2_passed=false，標記為 high-risk。
  - 每完成一小批任務（例如完成一個案例或新增一批引用）即執行快速回歸：`pytest -q tests/test_generator_json_pipeline.py` 與 `pytest -q tests/test_json_normalizer.py`，並將結果與耗時附註至 `metrics/plan_runs.csv`。
  - 每日統計 Stage 2 成功率（成功次數 ÷ 總次數）。低於 80% 時，優先檢視 metadata_filter 與引用品質。
- 嚴格 schema 失敗比率升高時：
  - 縮短 snippets 總長、提高欄位關聯權重、增加缺失策略明確性、或升級至更強模型
  - 觀察 `metrics/plan_runs.csv` 的 `stage2_feedback` 與 `retry_{n}` 記錄，鎖定重複缺失點。

與 S0/S1 的關係
- S0：直接 snippets → Schema（已在 docs/s0_vectors_to_strict_schema.md）
- S1：在 S0 加本地欄位抽取器（半結構化 extracted_params）
- S2（本方案）：把「規劃」變成一級公民，Plan JSON 可審計可快取；Schema Agent 專注填表。

驗收標準
- Agent 2 嚴格 JSON Schema 合格率提升，相較 S0/S1 幻覺與漏填顯著下降。
- Plan JSON 可驅動診斷（缺失/衝突/覆蓋）與持續優化（權重、控長、策略）。
- 延時與成本在可接受範圍（必要時以兩請求先行，成熟後再試單請求工具化）。
