Sanitizer 擴充設計說明（未來指南）

概觀
- 目前已實作：chains/generator.py 中的 sanitize_newvarcte(xml)
  - 功能：把 <newvarcte name="X" value="Y" .../> 轉為屬性式 <newvarcte ... X="Y" .../>。
  - 特性：保留其他屬性；處理自閉合/非自閉合；支援單/雙引號；對已正確者為冪等。
- 未來目標：將「單規則正則清洗」擴展為「可配置、可測、可觀測」的多規則 Sanitizer Pipeline。

設計目標
- 安全：不可破壞已正確輸出（冪等、可回退）。
- 可配置：以規則/策略驅動，而非硬編碼。
- 可驗證：單元測試、黃金檔（golden files）、度量與日誌。
- 易集成：仍在 generator_chain 最後一步執行，或提供 CLI/工具鏈用於離線修復。

擴充路線圖
1) 一般化「name/value → 屬性式」規則
- 動機：除了 newvarcte，未來可能出現其他標籤或不同鍵名（例如 key/value、param/value）。
- 作法：
  - 引入規則註冊表（registry），每條規則包含：
    - tag_name: 目標標籤（允許 * 或多個）
    - name_attr: 預設 "name"（可覆蓋）
    - value_attr: 預設 "value"（可覆蓋）
    - allowlist/denylist: 限制適用條件（例如僅在 /case/casedef/... 路徑）
  - 規則套用：先 match → 移除 name/value → 以 name 作為新屬性鍵、value 作為值 → 保留其他屬性 → 冪等。
- 配置示例（YAML）：
  rules:
    - type: name_value_to_attribute
      tag: newvarcte
      name_attr: name
      value_attr: value
    - type: name_value_to_attribute
      tag: param
      name_attr: key
      value_attr: value

2) 值正規化（Normalization）
- 目標：格式收斂，降低 downstream 解析風險。
- 子功能：
  - 布林歸一：true/false、0/1、yes/no → 指定標準（例如 "true"/"false" 或 "0"/"1"）。
  - 數字格式：去除不必要的尾零；科學記號統一；小數精度上限。
  - 單位處理（可選）：支援 "0.1 m" → 0.1（若 schema 嚴格 SI 且不保留單位字串）；或保留單位的正規化。
  - 去重與合併：同一標籤重複變數時，指定優先規則（保留第一次/最後一次/採用 Canon）。
- 配置示例：
  normalize:
    boolean: { format: "true_false" }  # 或 "zero_one"
    number: { max_decimals: 6, scientific: false }
    units: { mode: "strip" }           # 或 "keep", "convert_to_SI"

3) 屬性排序與去重
- 目的：穩定 diff 與生成，利於審查與測試。
- 作法：
  - 排序策略：字典序、Canon 序（先關鍵字段，如 mdbc, dom_padding, tank_min_x...）。
  - 去重策略：若同鍵出現多次，依規則決定保留一個（保留最後/最前/採 Canon fallback）。
- 配置示例：
  attributes:
    order: ["mdbc","dom_padding","tank_min_x","tank_max_x","tank_min_z","tank_max_z","*"]
    dedupe: "keep_last"  # 或 keep_first

4) Schema 白名單與結構校驗
- 目的：移除未知/非法屬性或節點，或升級為警告。
- 作法：
  - per-tag 屬性白名單（allowlist），未知屬性：
    - mode: "remove" | "warn" | "keep"
  - 節點層級校驗：指定 XPath 應存在/唯一/順序，與 Fixer Canon 同步。
- 配置示例：
  schema:
    tags:
      newvarcte:
        allow_attrs: ["mdbc","dom_padding","tank_min_x","tank_max_x","tank_min_z","tank_max_z","fluid_min_x","fluid_max_x","fluid_min_z","fluid_max_z"]
        unknown_attr: "warn"

5) 使用 XML 解析器 + XPath（取代/輔助正則）
- 動機：正則對巢狀、換行、縮排、命名空間等較脆弱。
- 作法：
  - 以 Python xml.etree.ElementTree 或 lxml.etree 解析、修改、序列化。
  - 小心事項：
    - 格式化：標準序列化會重排空白，必要時搭配 pretty printer 與 post-formatter。
    - 自閉合 vs 開閉：序列化策略需一致（可統一為自閉合）。
    - 命名空間（若未使用可忽略）。
- 建議：先維持目前正則針對簡單規則；新功能漸進引入 XML 解析器，提供一個選項 enable_xml_parser=true。

6) Pipeline 架構
- 介面：
  - def sanitize(xml: str, config: Optional[dict] = None) -> str
  - 內部步驟（每步都是 Rule）：for rule in rules: xml = rule.apply(xml_or_dom)
- Rule 類型：
  - RegexRule：快速處理單點文本替換。
  - XmlRule：基於 DOM/XPath 的結構化修改。
- 範例骨架（擬議檔案：chains/sanitizer.py）：
  class Sanitizer:
      def __init__(self, rules):
          self.rules = rules
      def apply(self, xml: str) -> str:
          ctx = xml
          for r in self.rules:
              ctx = r.apply(ctx)
          return ctx

  class NameValueToAttributeRule:
      def __init__(self, tag, name_attr="name", value_attr="value"):
          ...
      def apply(self, xml: str) -> str:
          # 目前 regex 版本；未來可切換 DOM 版本
          return transform(xml)

  def build_default_sanitizer(config: dict) -> Sanitizer:
      # 讀取 config.rules 與 normalize/schema/attributes 等段落，生成 rule 列表
      ...

7) 設定檔 Schema（YAML/JSON）
- 放置位置：configs/sanitizer.yaml（未來需要時新增）
- 內容：
  - rules: 規則列表（含類型與參數）
  - normalize/schema/attributes：策略層設定（供對應規則讀取）
  - parser: { engine: "regex" | "xml", pretty_print: false, self_close_style: "auto" }
- 最小示例：
  parser: { engine: "regex" }
  rules:
    - type: name_value_to_attribute
      tag: newvarcte
      name_attr: name
      value_attr: value
  normalize:
    boolean: { format: "true_false" }
    number: { max_decimals: 6, scientific: false }
  attributes:
    order: ["mdbc","dom_padding","*"]

8) 可觀測性與安全模式
- 日誌：Sanitizer 應可在 DSPH_DEBUG=1 時輸出每條規則進出長度、變更摘要（新增/刪除/修改的節點/屬性數）。
- Dry-run：提供 sanitize_dry_run(xml, config) → 返回差異摘要，不改動原文。
- 度量：規則命中率、修改次數、失敗/跳過次數。
- 失敗回退：單條規則拋異常時，回退到該規則前狀態並記錄警告，不中止整體管線（可配置）。

9) 測試策略
- 單元測試（現已新增 tests/test_predefinition_sanitizer.py）再擴充：
  - Property-based 測試（hypothesis）：隨機空白/引號/屬性順序。
  - Golden files：對固定輸入 XML 產生輸出並比對檔案內容。
  - Fuzz：插入未知屬性、大小寫混淆、換行/縮排、混合自閉合與非自閉合。
- 規約：每條規則至少有「非法→合法」「合法保持不變」兩類測例。

10) 整合點與 CLI
- generator_chain：維持「模型輸出 → extract_xml → sanitize(...) → 回傳」流程。
- CLI（可選）：新增 tools/cli_sanitize.py
  - 用法：python tools/cli_sanitize.py --in Case_Def.xml --out Case_Def_sanitized.xml --config configs/sanitizer.yaml --dry-run
  - 輸出差異摘要與統計。

未來代碼腳手架（範本）
- 新檔案 chains/sanitizer.py（未建立，僅規劃）
  class Sanitizer:
      def __init__(self, rules): self.rules = rules
      def apply(self, xml: str) -> str:
          out = xml
          for r in self.rules:
              try:
                  out2 = r.apply(out)
              except Exception as e:
                  # log warning; optionally rollback this rule
                  out2 = out
              out = out2
          return out

  class RegexNameValueToAttributeRule:
      def __init__(self, tag: str, name_attr: str = "name", value_attr: str = "value"):
          ...
      def apply(self, xml: str) -> str:
          # 基於目前 sanitize_newvarcte 的正則改寫成通用版本
          return transformed

  def build_sanitizer_from_config(cfg: dict) -> Sanitizer:
      # parse cfg and instantiate rules
      ...

- chains/generator.py 中替換：
  # 後續若導入泛化 Sanitizer：
  # cfg = load_yaml("configs/sanitizer.yaml") if os.path.exists(...) else {}
  # sanitizer = build_sanitizer_from_config(cfg) or default_sanitizer()
  # xml = sanitizer.apply(xml)

相容性與開關
- 預設：延續現有 sanitize_newvarcte，確保零風險。
- 開關：
  - SANITIZER_ENGINE=regex|xml：選擇解析器。
  - SANITIZER_CONFIG=configs/sanitizer.yaml：指向外部配置（存在且有效才啟用）。
  - SANITIZER_DRY_RUN=1：只做差異檢查，回傳原文與摘要。

性能考量
- 正則規則：對短小修補非常快，可優先保留。
- XML DOM：複雜規則時比較穩健，但需控制序列化帶來的改動幅度；建議 incremental adoption。
- 批量流程：對大檔案建議流式處理或 chunk-based（僅在必要時考慮）。

落地建議（現在不動碼；保留筆記）
- 暫不改動現有程式；僅把本文件作為設計備忘。
- 未來要擴充時，先新增 chains/sanitizer.py 與 configs/sanitizer.yaml，再把 generator_chain 的單行 sanitize_newvarcte 替換為 build_sanitizer_from_config(...).apply(...)。
- 先實作以下三條最低風險規則：
  1) name/value→屬性式（通用）
  2) 屬性排序（Canon + *）
  3) 布林/數字正規化（"true"/"false"、小數位上限）

下一步（決定要動時再做）
- 建立 chains/sanitizer.py 與對應測試 tests/test_sanitizer_pipeline.py。
- 增加 configs/sanitizer.yaml（最小可用集）。
- 在 chains/generator.py 切入新 Sanitizer（保留環境變數開關與 fallback）。
- 擴充測試涵蓋 DOM/正則雙引擎（可選）。

結語
- 本文件是未來擴充的詳細藍圖。現階段僅需保留此規劃；當再次遇到類似問題或需要更通用的清洗能力時，按上述路線圖逐步引入即可，並保持「小步快跑、可回退、可驗證」原則。
