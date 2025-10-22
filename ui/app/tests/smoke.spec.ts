import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import App from '../src/App';
import type { ArtifactMetadata, LogEntry, MetricsSnapshot, RunSummary } from '../src/types/runs';

vi.mock('../src/services/api', async () => {
  const actual = await vi.importActual<typeof import('../src/services/api')>('../src/services/api');
  const mockClient = {
    listRuns: vi.fn(),
    getRun: vi.fn(),
    getRunLogs: vi.fn(),
    getRunMetrics: vi.fn(),
    getRunArtifacts: vi.fn(),
    deleteRun: vi.fn(),
    fetchArtifactContent: vi.fn(),
  } satisfies Partial<typeof actual.apiClient>;
  return { ...actual, apiClient: mockClient };
});

const { apiClient } = await import('../src/services/api');

describe('UI smoke flow', () => {
  let queryClient: QueryClient;
  let clipboardWriteMock: ReturnType<typeof vi.fn>;
  const sampleRun: RunSummary = {
    runId: 'RUN-1',
    query: 'Generate dambreak',
    status: 'success',
    exitCode: 0,
    startedAt: '2025-10-21T14:05:12Z',
    finishedAt: '2025-10-21T14:12:44Z',
    durationSeconds: 452.8,
    stageCheckpoints: [
      {
        step: 'init',
        state: 'completed',
        startedAt: '2025-10-21T14:05:12Z',
        finishedAt: '2025-10-21T14:05:20Z',
      },
      {
        step: 'sim',
        state: 'completed',
        startedAt: '2025-10-21T14:05:20Z',
        finishedAt: '2025-10-21T14:12:00Z',
      },
      {
        step: 'post',
        state: 'completed',
        startedAt: '2025-10-21T14:12:00Z',
        finishedAt: '2025-10-21T14:12:44Z',
      },
    ],
    stepStatus: [
      { step: 'reference_search', state: 'completed' },
      { step: 'config_generation', state: 'completed' },
      { step: 'execution', state: 'skipped' },
    ],
  };
  const sampleLogs: LogEntry[] = [
    { runId: 'RUN-1', sequence: 1, message: 'start' },
    { runId: 'RUN-1', sequence: 2, message: 'done' },
  ];
  const sampleMetrics: MetricsSnapshot = {
    runId: 'RUN-1',
    capturedAt: '2025-10-21T14:12:50Z',
    durationSeconds: 452.8,
    resourceUsage: [
      {
        capturedAt: '2025-10-21T14:05:15Z',
        cpuPercent: 55,
        memoryPercent: 72,
        gpu: [{ name: 'RTX 4090', utilizationPercent: 68 }],
      },
    ],
  };
  const sampleArtifacts: ArtifactMetadata[] = [
    { runId: 'RUN-1', path: 'generated_case.xml', label: 'Generated XML case' },
  ];

  beforeEach(() => {
    clipboardWriteMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: clipboardWriteMock },
      configurable: true,
    });

    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    (apiClient.listRuns as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([sampleRun]);
    (apiClient.getRun as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(sampleRun);
    (apiClient.getRunLogs as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(sampleLogs);
    (apiClient.getRunMetrics as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleMetrics,
    );
    (apiClient.getRunArtifacts as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleArtifacts,
    );
    (apiClient.deleteRun as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    (apiClient.fetchArtifactContent as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      '<xml />',
    );
  });

  afterEach(() => {
    cleanup();
    queryClient.clear();
    delete (navigator as Record<string, unknown>).clipboard;
    vi.clearAllMocks();
  });

  test('displays run progress and resources', async () => {
    render(
      React.createElement(
        QueryClientProvider,
        { client: queryClient },
        React.createElement(
          MemoryRouter,
          { initialEntries: ['/'] },
          React.createElement(App, null),
        ),
      ),
    );

    const runCard = await screen.findByRole('link', { name: /open run run-1/i });
    expect(runCard).toBeInTheDocument();
    fireEvent.click(runCard);

    await waitFor(() => expect(screen.getByText(/Initialization/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('tab', { name: /Metrics/i }));
    expect(await screen.findByText(/Resource Usage/i)).toBeInTheDocument();
    expect(await screen.findByText(/CPU 55.0%/i)).toBeInTheDocument();
  });
});
