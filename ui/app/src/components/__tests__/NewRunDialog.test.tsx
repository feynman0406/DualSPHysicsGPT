import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import NewRunDialog from '../NewRunDialog';

afterEach(() => {
  cleanup();
});

describe('NewRunDialog', () => {
  it('validates STL file selection and displays summary', () => {
    const handleSubmit = vi.fn();
    render(
      <NewRunDialog
        open
        onClose={() => undefined}
        onSubmit={handleSubmit}
        errorMessage={null}
      />,
    );

    const fileInput = screen.getByLabelText(/upload stl file/i) as HTMLInputElement;

    const invalidFile = new File(['solid'], 'invalid.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [invalidFile] } });
    expect(screen.getByText(/must use the \.stl extension/i)).toBeInTheDocument();

    const validFile = new File(['solid'], 'geometry.stl', { type: 'application/sla' });
    fireEvent.change(fileInput, { target: { files: [validFile] } });

    expect(screen.queryByText(/must use the \.stl extension/i)).toBeNull();
    expect(screen.getByText('geometry.stl')).toBeInTheDocument();
    expect(screen.getByText(/Binary or ASCII/i)).toBeInTheDocument();
  });
});
