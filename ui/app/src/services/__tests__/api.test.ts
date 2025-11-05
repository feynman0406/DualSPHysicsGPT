import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../api';

const originalFetch = global.fetch;

const mockResponse = <T,>(data: T) => ({
  ok: true,
  json: vi.fn().mockResolvedValue(data),
});

afterEach(() => {
  vi.restoreAllMocks();
  global.fetch = originalFetch;
});

describe('ApiClient createRun', () => {
  it('sends JSON payload when no external STL is provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ runId: 'RUN-JSON', status: 'queued' }));
    global.fetch = fetchMock as unknown as typeof fetch;

    await apiClient.createRun({ query: 'demo run', pauseAfterAgent1: true, execute: false });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/runs');
    expect(options).toMatchObject({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const body = (options as RequestInit).body as string;
    expect(JSON.parse(body)).toEqual({
      query: 'demo run',
      pauseAfterAgent1: true,
      execute: false,
    });
  });

  it('sends FormData when an external STL is present', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ runId: 'RUN-STL', status: 'queued' }));
    global.fetch = fetchMock as unknown as typeof fetch;

    const file = new File(['solid'], 'mesh.stl', { type: 'application/sla' });

    await apiClient.createRun({
      query: 'with stl',
      pauseAfterAgent1: false,
      execute: true,
      externalStl: file,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    expect(options?.headers).toBeUndefined();
    const body = options?.body;
    expect(body).toBeInstanceOf(FormData);
    const form = body as FormData;
    expect(form.get('query')).toBe('with stl');
    expect(form.get('pauseAfterAgent1')).toBe('false');
    expect(form.get('execute')).toBe('true');
    expect(form.get('externalStl')).toBeInstanceOf(File);
  });
});
describe('ApiClient getRun', () => {
  it('parses dependency metadata and manifest', async () => {
    const payload = {
      runId: 'RUN-DEPS',
      query: 'dependency demo',
      status: 'success',
      summary: {
        artifactCount: 2,
        dependencyCount: 3,
        dependencyWarnings: 1,
      },
      dependencyManifest: {
        run_id: 'RUN-DEPS',
        generated_at: '2025-11-03T12:20:00Z',
        files: [
          {
            path: 'logs/resources/asset.txt',
            purpose: 'Config reference',
            source: 'declared',
            status: 'copied',
            copied_path: 'external_files/logs/resources/asset.txt',
            notes: ['copied successfully'],
          },
        ],
        warnings: ['Missing backup asset'],
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(payload));
    global.fetch = fetchMock as unknown as typeof fetch;

    const run = await apiClient.getRun('RUN-DEPS');

    expect(run.summary?.dependencyCount).toBe(3);
    expect(run.summary?.dependencyWarnings).toBe(1);
    expect(run.dependencyManifest?.runId).toBe('RUN-DEPS');
    expect(run.dependencyManifest?.files).toHaveLength(1);
    const file = run.dependencyManifest?.files?.[0];
    expect(file?.copiedPath).toBe('external_files/logs/resources/asset.txt');
    expect(file?.notes).toEqual(['copied successfully']);
    expect(run.dependencyManifest?.warnings).toEqual(['Missing backup asset']);
  });

  it('builds dependency download URLs using the artifact endpoint', () => {
    const url = apiClient.buildDependencyDownloadUrl('RUN-123', 'external_files/foo.stl');
    const parsed = new URL(url);
    expect(parsed.pathname).toContain('/api/runs/RUN-123/artifacts/download');
    expect(parsed.searchParams.get('path')).toBe('external_files/foo.stl');
  });
});

