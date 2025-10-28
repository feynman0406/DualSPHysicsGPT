import { z } from 'zod';
import type {
  ArtifactMetadata,
  CreateRunRequest,
  CreateRunResponse,
  LogEntry,
  MetricsSnapshot,
  RunSummary,
  StepDetailPayload,
} from '../types/runs';

const API_BASE_URL = '/api';

const stageStatusSchema = z.object({
  step: z.string(),
  state: z.enum(['idle', 'pending', 'running', 'completed', 'failed', 'skipped']),
  startedAt: z.string().optional(),
  finishedAt: z.string().optional(),
  reason: z.string().optional(),
  message: z.string().optional(),
});

const runSummaryDetailsSchema = z.object({
  primaryOutput: z.string().optional(),
  artifactCount: z.number().optional(),
  hasFailures: z.boolean().optional(),
  externalStl: z
    .object({
      filename: z.string(),
      sizeBytes: z.number().optional(),
    })
    .nullable()
    .optional(),
  externalStlAttached: z.boolean().optional(),
});
const runSummarySchema = z.object({
  runId: z.string(),
  query: z.string().default(''),
  status: z.enum(['queued', 'running', 'success', 'failed', 'interrupted']),
  exitCode: z.number().nullable().optional(),
  startedAt: z.string().optional(),
  finishedAt: z.string().optional(),
  durationSeconds: z.number().optional(),
  modelName: z.string().optional(),
  reasoningLevel: z.string().optional(),
  reasoningConfig: z.record(z.string()).optional(),
  summary: runSummaryDetailsSchema.optional(),
  stepStatus: z.array(stageStatusSchema).optional(),
  stageCheckpoints: z.array(stageStatusSchema).optional(),
});

const logEntrySchema = z.object({
  runId: z.string(),
  sequence: z.number(),
  timestampRelative: z.number().optional(),
  timestampUtc: z.string().optional(),
  stream: z.string().optional(),
  message: z.string(),
});

const resourceUsageSchema = z.object({
  capturedAt: z.string(),
  cpuPercent: z.number().optional(),
  memoryPercent: z.number().optional(),
  memoryUsedMb: z.number().optional(),
  memoryTotalMb: z.number().optional(),
  gpu: z
    .array(
      z.object({
        name: z.string(),
        utilizationPercent: z.number().optional(),
        memoryUsedMb: z.number().optional(),
        memoryTotalMb: z.number().optional(),
      }),
    )
    .optional(),
  notes: z.array(z.string()).optional(),
});

const metricsSchema = z.object({
  runId: z.string(),
  capturedAt: z.string(),
  durationSeconds: z.number().optional(),
  tokenUsage: z
    .object({
      input: z.number().optional(),
      output: z.number().optional(),
      costUsd: z.number().optional(),
    })
    .optional(),
  retrieval: z
    .object({
      recallAt5: z.number().optional(),
      totalSources: z.number().optional(),
    })
    .optional(),
  stepDurations: z.record(z.number()).optional(),
  baselineDelta: z
    .object({
      durationPercent: z.number().optional(),
      costPercent: z.number().optional(),
    })
    .optional(),
  resourceUsage: z.array(resourceUsageSchema).optional(),
});

const artifactSchema = z.object({
  runId: z.string(),
  path: z.string(),
  label: z.string().optional(),
  sizeBytes: z.number().optional(),
  sha256: z.string().optional(),
  mimeType: z.string().optional(),
  previewAvailable: z.boolean().optional(),
  downloadUrl: z.string().optional(),
  baselineComparable: z.boolean().optional(),
});

const stepDetailSchema = z.object({
  runId: z.string(),
  step: z.string(),
  overview: z
    .object({
      inputPrompt: z.string().optional(),
      retrievedReferences: z
        .array(
          z.object({
            filename: z.string(),
            score: z.number().optional(),
          }),
        )
        .optional(),
      parameterChanges: z
        .array(
          z.object({
            path: z.string(),
            from: z.unknown().optional(),
            to: z.unknown().optional(),
          }),
        )
        .optional(),
    })
    .optional(),
  logs: z
    .object({ firstSequence: z.number().optional(), lastSequence: z.number().optional() })
    .optional(),
  artifacts: z.array(z.string()).optional(),
  status: z.enum(['pending', 'running', 'completed', 'failed']).optional(),
});

const createRunSchema = z.object({
  runId: z.string(),
  status: z.enum(['queued', 'running', 'success', 'failed', 'interrupted']),
});

const zArray = <T extends z.ZodTypeAny>(schema: T) => z.array(schema);

async function parseJson<T>(response: Response, schema: z.ZodSchema<T>): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }

  const json = await response.json();
  return schema.parse(json);
}

const appendFormBoolean = (form: FormData, key: string, value: boolean | undefined) => {
  if (value !== undefined) {
    form.append(key, value ? 'true' : 'false');
  }
};


export class ApiClient {
  constructor(private readonly baseUrl: string = API_BASE_URL) {}

  private resolveArtifactUrl(artifact: ArtifactMetadata, runIdOverride?: string): string {
    if (artifact.downloadUrl) {
      return artifact.downloadUrl;
    }
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
    const effectiveRunId = artifact.runId ?? runIdOverride;
    if (!effectiveRunId) {
      throw new Error('Artifact runId is not available for preview.');
    }
    const url = new URL(`${this.baseUrl}/runs/${effectiveRunId}/artifacts/content`, origin);
    url.searchParams.set('path', artifact.path);
    return url.toString();
  }

  async listRuns(): Promise<RunSummary[]> {
    const response = await fetch(`${this.baseUrl}/runs`);
    return parseJson(response, zArray(runSummarySchema)) as Promise<RunSummary[]>;
  }

  async getRun(runId: string): Promise<RunSummary> {
    const response = await fetch(`${this.baseUrl}/runs/${runId}`);
    return parseJson(response, runSummarySchema) as Promise<RunSummary>;
  }

  async createRun(body: CreateRunRequest): Promise<CreateRunResponse> {
    const { externalStl, ...payload } = body;

    let response: Response;
    if (externalStl instanceof File) {
      const form = new FormData();
      form.append('query', payload.query);
      appendFormBoolean(form, 'pauseAfterAgent1', payload.pauseAfterAgent1);
      appendFormBoolean(form, 'execute', payload.execute);
      form.append('externalStl', externalStl, externalStl.name || 'external.stl');
      response = await fetch(`${this.baseUrl}/runs`, {
        method: 'POST',
        body: form,
      });
    } else {
      response = await fetch(`${this.baseUrl}/runs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
    }

    return parseJson(response, createRunSchema) as Promise<CreateRunResponse>;
  }
  async deleteRun(runId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/runs/${runId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
  }


  async getRunLogs(runId: string, params?: { fromSequence?: number }): Promise<LogEntry[]> {
    const query = params?.fromSequence ? `?from=${params.fromSequence}` : '';
    const response = await fetch(`${this.baseUrl}/runs/${runId}/logs${query}`);
    return parseJson(response, zArray(logEntrySchema)) as Promise<LogEntry[]>;
  }

  async getRunMetrics(runId: string): Promise<MetricsSnapshot | null> {
    const response = await fetch(`${this.baseUrl}/runs/${runId}/metrics`);
    if (response.status === 204) {
      return null;
    }
    return parseJson(response, metricsSchema) as Promise<MetricsSnapshot>;
  }

  async getRunArtifacts(runId: string): Promise<ArtifactMetadata[]> {
    const response = await fetch(`${this.baseUrl}/runs/${runId}/artifacts`);
    return parseJson(response, zArray(artifactSchema)) as Promise<ArtifactMetadata[]>;
  }

  async getStepDetail(runId: string, step: string): Promise<StepDetailPayload> {
    const response = await fetch(`${this.baseUrl}/runs/${runId}/steps/${step}`);
    return parseJson(response, stepDetailSchema) as Promise<StepDetailPayload>;
  }

  async fetchArtifactContent(artifact: ArtifactMetadata, runIdOverride?: string): Promise<string> {
    const target = this.resolveArtifactUrl(artifact, runIdOverride);
    const response = await fetch(target);
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.text();
  }
}

export const apiClient = new ApiClient();

export const __mocks = {
  buildMockClient(overrides: Partial<ApiClient> = {}): ApiClient {
    return Object.assign(new ApiClient('/__mock__'), overrides);
  },
};



