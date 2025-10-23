# UI State Matrix

This matrix summarises the expected visual and interactive states for core UI surfaces. Descriptions assume data is sourced from the Phase 1 runner contract and augmented with planned telemetry.

| View | Idle | Running | Success | Failure |
| --- | --- | --- | --- | --- |
| Run List | Displays cached runs sorted by start time, filters cleared, controls enabled. | Polls for new runs every 15 s, injects skeleton rows for pending items, disables destructive actions. | Highlights latest completed run, surfaces duration deltas vs baseline. | Shows inline banner describing fetch error; retains last known data with retry control. |
| Run Detail (header) | Shows metadata once selected run loads; stage progress bar renders init/sim/post states above the stepper; secondary actions (rerun, download) enabled if data ready. | Progress indicator pulses, segmented stage bar highlights the active segment while timestamps update live. | Banner switches to final outcome with duration; stage segments all marked completed; rerun re-enabled; completion timestamp locked. | Banner turns red with summary from RunResponse.error; failed stage flagged; offers retry and link to diagnostics. |
| Stepper | All steps greyed until data fetched; first actionable step auto-selected. | Active step animates; upcoming steps disabled; context banner shows current agent. | Completed steps marked with check icons text; user can revisit steps freely. | Failed step marked in red; downstream steps locked until rerun. |
| Logs Tab | Placeholder message prompting user to open log stream. | Streams latest log lines with autoscroll; search box disabled while buffer warms. | Scrollable log with search and filters enabled; download button active. | Error overlay with explanation; offers retry fetch while retaining last partial log. |
| Metrics Tab | Shows placeholders with baseline target hints. | Displays spinners and interim values (eg remaining time) as telemetry arrives, including resource usage notes when GPU metrics are unavailable. | Filled cards, trend charts active; resource widget shows CPU %, memory, and GPU utilisation; deviations annotated in amber when outside thresholds. | Cards show N/A labels; callout lists missing signals required from backend, including telemetry fallbacks. |
| Artifact Viewer | Tree renders from cached manifest; preview placeholder instructs to select a file. | Loading skeleton for manifest; preview area shows spinner until file fetched. | Preview renders with syntax highlighting and metadata; diff control enabled when baseline present. | Error toast near toolbar; failed file nodes tagged with warning icon text and retry option. |

### Cross-view behaviours
- Empty state: when no runs exist, Run List shows onboarding panel with link to documentation; other views remain disabled.
- Connectivity loss: global banner appears; views fall back to cached content until connection restored.
- Permission errors propagate to Failure column behaviours and log a telemetry event for audit.
