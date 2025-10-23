# Phase 2 Wireframes

These low-fidelity wireframes illustrate the core UI surfaces scoped for the DualSPHysics runner integration. Layouts emphasise information hierarchy, with responsive stacking implied for narrow viewports.

## Run List

```text
+--------------------------------------------------------------------------------+
| Header: DualSPHysics Runs            [New Run] [Filters v] [Refresh]           |
+--------------------------------------------------------------------------------+
| Search [?] [__________________________________________]   Status: [All v]      |
+--------------------------------------------------------------------------------+
| Run Row +-------------------------------+ Run Row +--------------------------+ |
|         | [Success] CASE-20251021-01    |         | [Running] CASE-20251021-02| |
|         | "2D dambreak 2 m"            |         | "Sloshing tank sweep"     | |
|         | Triggered 2025-10-21 14:05   |         | Triggered 2025-10-21 15:18| |
|         | Duration 00:07:32            |         | Step 2 of 3               | |
|         +-------------------------------+         +--------------------------+ |
| ...                                                                            |
+--------------------------------------------------------------------------------+
| Pagination < Prev | Page 1 of 5 | Next >                                      |
+--------------------------------------------------------------------------------+
```

Key interactions: run cards are clickable to open the detail view; quick filters for status and time; primary call-to-action opens the run submission modal.

## Run Detail (Stepper)

```text
+--------------------------------------------------------------------------------+
| Breadcrumb: Runs > CASE-20251021-01 "2D dambreak 2 m"                          |
+--------------------------------------------------------------------------------+
| Status Banner: [Success] Started 14:05 | Duration 00:07:32 | Rerun             |
+--------------------------------------------------------------------------------+
| Stepper: [1 Reference Search done]-->[2 Config Generation done]-->[3 Execution]|
+--------------------------------------------------------------------------------+
| Step Panel Header: Step 2 - Config Generation                                  |
| Tabs: Overview | Logs | Metrics | Artifacts                                    |
+--------------------------------------------------------------------------------+
| Overview pane (split):                                                         |
| +--------------------------+ +----------------------------------------------+ |
| | Highlight Cards          | | Step Summary                                 | |
| | - Inputs                 | | - Prompt                                     | |
| | - Key Outputs            | | - Retrieved references                       | |
| | - Next Actions           | | - Parameter deltas vs template               | |
| +--------------------------+ +----------------------------------------------+ |
+--------------------------------------------------------------------------------+
```

The stepper stays pinned while the content area swaps between tabs. Each step provides agent context plus actions such as downloading generated config or opening prompts.

## Log Viewer

```text
+--------------------------------------------------------------------------------+
| Log Toolbar: [Search __________________]  [Filter: stdout+stderr v]  [Download] |
+--------------------------------------------------------------------------------+
| Timestamp mode: ( ) Relative  ( ) Absolute     Autoscroll: [On]                |
+--------------------------------------------------------------------------------+
| 00:00 | ENVIRONMENT CHECK                                                       |
| 00:01 | OPENAI_API_KEY: ********************                                    |
| 00:12 | [Step 1/3] Searching vector store...                                    |
| 02:43 | File search complete - found 15 sources                                 |
| 04:15 | [Step 2/3] Analyzing references...                                      |
| ...                                                                            |
+--------------------------------------------------------------------------------+
```

The viewer supports search, filtering once structured streams are available, and downloading the combined log.

## Metrics Widgets

```text
+--------------------------------------------------------------------------------+
| Metrics Header: Run Health                                                     |
+--------------------------------------------------------------------------------+
| +---------------+ +--------------+ +------------------------------+            |
| | Duration      | | Tokens Used  | | Retrieval Recall at 5        |            |
| | 00:07:32      | | Input 45000  | | 80 percent (target >= 75)    |            |
| | vs baseline +2| | Output 12000 | | Trend sparkline              |            |
| +---------------+ +--------------+ +------------------------------+            |
| +------------------------------+ +------------------------------------------+ |
| | Cost Estimate (USD)         | | Timeline Chart: Step durations            | |
| | 3.42                        | | - Reference Search 02:43                  | |
| | vs budget 5.00              | | - Config Generation 03:12                 | |
| +------------------------------+ | - Execution 01:37                         | |
|                                 | Bars show deviation from baseline         | |
|                                 +------------------------------------------+ |
+--------------------------------------------------------------------------------+
```

Widgets highlight deviations from baseline runs and integrate cost and duration trendlines.

## Artifact Viewer

```text
+--------------------------------------------------------------------------------+
| Artifact Toolbar: [List v]  Sort: [Last Modified v]  [Compare] [Download All]  |
+--------------------------------------------------------------------------------+
| Sidebar (tree)         | Preview Pane                                          |
| agent1_output.json     | +--------------------------------------------------+ |
| agent2_input.json      | | Filename: agent2_config.json                      | |
| agent2_config.json     | | Size: 18.5 KB | SHA256: 22a1...                   | |
| generated_case.xml     | |                                                  | |
| diagnostics/           | | Structured preview (JSON tree or syntax view)    | |
|                        | | [View Raw] [Open in new tab]                     | |
|                        | |                                                  | |
|                        | | Diff Mode: select baseline to compare inline     | |
|                        | +--------------------------------------------------+ |
+--------------------------------------------------------------------------------+
```

Artifacts surface metadata, syntax-aware previews, and optional diffing with baseline runs. Layout supports tree navigation for nested outputs.
