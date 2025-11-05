export interface DependencyFile {
  path: string;
  purpose?: string;
  source?: string;
  status?: string;
  copiedPath?: string;
  notes?: string[];
  [key: string]: unknown;
}

export interface DependencyManifest {
  runId?: string;
  generatedAt?: string;
  files: DependencyFile[];
  warnings?: string[];
  [key: string]: unknown;
}

export interface RunSummaryDetails {
  primaryOutput?: string;
  artifactCount?: number;
  hasFailures?: boolean;
  externalStl?: {
    filename: string;
    sizeBytes?: number;
  } | null;
  externalStlAttached?: boolean;
  dependencyCount?: number;
  dependencyWarnings?: number;
}

export type RunStatus = 'queued' | 'running' | 'success' | 'failed' | 'interrupted';

export interface RunStepStatus {
  step: string;
  state: 'idle' | 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  startedAt?: string;
  finishedAt?: string;
  reason?: string;
  message?: string;
}

export interface RunSummary {
  runId: string;
  query: string;
  model?: string;
  status: RunStatus;
  exitCode?: number | null;
  startedAt?: string;
  finishedAt?: string;
  durationSeconds?: number;
  modelName?: string;
  reasoningLevel?: string;
  reasoningConfig?: Record<string, string>;
  summary?: RunSummaryDetails;
  dependencyManifest?: DependencyManifest;
  stepStatus?: RunStepStatus[];
  stageCheckpoints?: RunStepStatus[];
}

export interface LogEntry {
  runId: string;
  sequence: number;
  timestampRelative?: number;
  timestampUtc?: string;
  stream?: string;
  message: string;
}

export interface ResourceUsageSample {
  capturedAt: string;
  cpuPercent?: number;
  memoryPercent?: number;
  memoryUsedMb?: number;
  memoryTotalMb?: number;
  gpu?: Array<{
    name: string;
    utilizationPercent?: number;
    memoryUsedMb?: number;
    memoryTotalMb?: number;
  }>;
  notes?: string[];
}

export interface MetricsSnapshot {
  runId: string;
  capturedAt: string;
  durationSeconds?: number;
  tokenUsage?: {
    input?: number;
    output?: number;
    costUsd?: number;
  };
  retrieval?: {
    recallAt5?: number;
    totalSources?: number;
  };
  stepDurations?: Record<string, number>;
  baselineDelta?: {
    durationPercent?: number;
    costPercent?: number;
  };
  resourceUsage?: ResourceUsageSample[];
}

export interface ArtifactMetadata {
  runId: string;
  path: string;
  label?: string;
  sizeBytes?: number;
  sha256?: string;
  mimeType?: string;
  previewAvailable?: boolean;
  downloadUrl?: string;
  baselineComparable?: boolean;
}

export interface StepDetailPayload {
  runId: string;
  step: string;
  overview?: {
    inputPrompt?: string;
    retrievedReferences?: Array<{ filename: string; score?: number }>;
    parameterChanges?: Array<{ path: string; from?: unknown; to?: unknown }>;
  };
  logs?: {
    firstSequence?: number;
    lastSequence?: number;
  };
  artifacts?: string[];
  status?: 'pending' | 'running' | 'completed' | 'failed';
}

export interface CreateRunRequest {
  query: string;
  model?: string;
  pauseAfterAgent1?: boolean;
  execute?: boolean;
  externalStl?: File | null;
}

export interface CreateRunResponse {
  runId: string;
  status: RunStatus;
}

