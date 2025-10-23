import { FormEvent, useEffect, useState } from 'react';
import './NewRunDialog.css';

export interface NewRunFormValues {
  query: string;
  pauseAfterAgent1: boolean;
  execute: boolean;
}

interface NewRunDialogProps {
  open: boolean;
  busy?: boolean;
  errorMessage?: string | null;
  onClose: () => void;
  onSubmit: (values: NewRunFormValues) => void;
}

const defaultValues: NewRunFormValues = {
  query: '',
  pauseAfterAgent1: false,
  execute: false,
};

const NewRunDialog = ({ open, onClose, onSubmit, busy, errorMessage }: NewRunDialogProps) => {
  const [values, setValues] = useState<NewRunFormValues>(defaultValues);

  useEffect(() => {
    if (open) {
      setValues(defaultValues);
    }
  }, [open]);

  if (!open) {
    return null;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit(values);
  };

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-run-title"
        className="dialog"
        onClick={event => event.stopPropagation()}
      >
        <header className="dialog-header">
          <h2 id="new-run-title">Trigger new run</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <form className="dialog-body" onSubmit={handleSubmit}>
          {errorMessage ? (
            <div className="dialog-error" role="alert">
              {errorMessage}
            </div>
          ) : null}
          <label className="field">
            <span>Query</span>
            <textarea
              required
              rows={4}
              value={values.query}
              placeholder="Describe the DualSPHysics scenario to run"
              onChange={event => setValues(prev => ({ ...prev, query: event.target.value }))}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={values.pauseAfterAgent1}
              onChange={event =>
                setValues(prev => ({ ...prev, pauseAfterAgent1: event.target.checked }))
              }
            />
            <span>Pause after Agent 1 completes retrieval</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={values.execute}
              onChange={event => setValues(prev => ({ ...prev, execute: event.target.checked }))}
            />
            <span>Execute GenCase after config generation</span>
          </label>
          <footer className="dialog-footer">
            <button type="button" className="ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="primary" disabled={busy}>
              {busy ? 'Triggering…' : 'Trigger run'}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
};

export default NewRunDialog;
