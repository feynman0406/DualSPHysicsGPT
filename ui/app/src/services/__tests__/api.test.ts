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
