import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ArtifactViewer from '../ArtifactViewer';
import type { ArtifactMetadata } from '../../types/runs';

const sampleArtifact: ArtifactMetadata = {
  runId: 'RUN-123',
  path: 'output/report.txt',
  label: 'Simulation report',
  previewAvailable: true,
  downloadUrl: 'https://example.test/report.txt',
  sizeBytes: 2048,
};

describe('ArtifactViewer copy preview control', () => {
  let writeTextMock: ReturnType<typeof vi.fn>;
  let execCommandMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeTextMock = vi.fn().mockResolvedValue(undefined);
    execCommandMock = vi.fn().mockReturnValue(true);

    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextMock },
      configurable: true,
    });

    Object.defineProperty(document, 'execCommand', {
      value: execCommandMock,
      configurable: true,
    });
  });

  afterEach(() => {
    delete (navigator as Record<string, unknown>).clipboard;
    delete (document as Record<string, unknown>).execCommand;
  });

  const waitForReset = () =>
    act(async () => {
      await new Promise(resolve => setTimeout(resolve, 2100));
    });

  it('copies the preview text when the clipboard API succeeds', async () => {
    const loadContent = vi.fn().mockResolvedValue('Preview content ready');

    render(
      <ArtifactViewer
        artifacts={[sampleArtifact]}
        isLoading={false}
        error={undefined}
        onRefresh={vi.fn()}
        loadContent={loadContent}
      />,
    );

    const copyButton = await screen.findByRole('button', { name: 'Copy artifact preview' });

    fireEvent.click(copyButton);

    expect(writeTextMock).toHaveBeenCalledWith('Preview content ready');

    await waitFor(() => expect(copyButton).toHaveTextContent('Copied!'));

    await waitForReset();

    await waitFor(() => expect(copyButton).toHaveTextContent('Copy preview'));
  });

  it('shows error feedback when all clipboard strategies fail', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    writeTextMock.mockRejectedValueOnce(new Error('no clipboard access'));
    execCommandMock.mockReturnValue(false);

    const loadContent = vi.fn().mockResolvedValue('Preview content ready');

    render(
      <ArtifactViewer
        artifacts={[sampleArtifact]}
        isLoading={false}
        error={undefined}
        onRefresh={vi.fn()}
        loadContent={loadContent}
      />,
    );

    const copyButton = await screen.findByRole('button', { name: 'Copy artifact preview' });

    fireEvent.click(copyButton);

    expect(writeTextMock).toHaveBeenCalledWith('Preview content ready');

    await waitFor(() => expect(copyButton).toHaveTextContent('Copy failed'));

    await waitForReset();

    await waitFor(() => expect(copyButton).toHaveTextContent('Copy preview'));

    consoleErrorSpy.mockRestore();
  });
});
