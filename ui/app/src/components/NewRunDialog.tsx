import { ChangeEvent, DragEvent, FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import './NewRunDialog.css';
import { formatFileSize } from '../utils/files';

export interface NewRunFormValues {
  query: string;
  pauseAfterAgent1: boolean;
  execute: boolean;
  externalStl: File | null;
}

interface NewRunDialogProps {
  open: boolean;
  busy?: boolean;
  errorMessage?: string | null;
  onClose: () => void;
  onSubmit: (values: NewRunFormValues) => void;
}

const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024;

const defaultValues: NewRunFormValues = {
  query: '',
  pauseAfterAgent1: false,
  execute: false,
  externalStl: null,
};

const NewRunDialog = ({ open, onClose, onSubmit, busy, errorMessage }: NewRunDialogProps) => {
  const [values, setValues] = useState<NewRunFormValues>(defaultValues);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (open) {
      setValues(defaultValues);
      setFileError(null);
      setIsDragOver(false);
    }
  }, [open]);

  if (!open) {
    return null;
  }

  const handleFileCandidate = (file: File | null) => {
    if (!file) {
      setValues(prev => ({ ...prev, externalStl: null }));
      setFileError(null);
      return;
    }

    const name = file.name.trim();
    const lower = name.toLowerCase();
    if (!lower.endsWith('.stl')) {
      setValues(prev => ({ ...prev, externalStl: null }));
      setFileError('File must use the .stl extension.');
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setValues(prev => ({ ...prev, externalStl: null }));
      setFileError('File exceeds the 25 MB limit.');
      return;
    }

    setValues(prev => ({ ...prev, externalStl: file }));
    setFileError(null);
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
    handleFileCandidate(file);
    if (event.target.value) {
      event.target.value = '';
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
    if (busy) {
      return;
    }
    const files = event.dataTransfer?.files;
    handleFileCandidate(files && files.length > 0 ? files[0] : null);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (busy) {
      return;
    }
    setIsDragOver(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
  };

  const handleDropZoneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openFilePicker();
    }
  };

  const handleRemoveFile = () => {
    handleFileCandidate(null);
  };

  const openFilePicker = () => {
    if (busy) {
      return;
    }
    fileInputRef.current?.click();
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit(values);
  };

  const selectedFile = values.externalStl;

  return (
    <div className='dialog-backdrop' role='presentation' onClick={onClose}>
      <div
        role='dialog'
        aria-modal='true'
        aria-labelledby='new-run-title'
        className='dialog'
        onClick={event => event.stopPropagation()}
      >
        <header className='dialog-header'>
          <h2 id='new-run-title'>Trigger new run</h2>
          <button type='button' className='icon-button' onClick={onClose} aria-label='Close'>
            X
          </button>
        </header>
        <form className='dialog-body' onSubmit={handleSubmit}>
          {errorMessage ? (
            <div className='dialog-error' role='alert'>
              {errorMessage}
            </div>
          ) : null}
          <label className='field'>
            <span>Query</span>
            <textarea
              required
              rows={4}
              value={values.query}
              placeholder='Describe the DualSPHysics scenario to run'
              onChange={event => setValues(prev => ({ ...prev, query: event.target.value }))}
            />
          </label>
          <label className='field file-field'>
            <span>External STL (optional)</span>
            <div
              className={`file-dropzone${isDragOver ? ' dragover' : ''}`}
              role='button'
              tabIndex={0}
              aria-disabled={busy}
              onClick={event => {
                event.preventDefault();
                openFilePicker();
              }}
              onKeyDown={handleDropZoneKeyDown}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type='file'
                accept='.stl'
                className='file-input'
                onChange={handleFileInputChange}
                disabled={busy}
                aria-label='Upload STL file'
              />
              <div className='file-dropzone-copy'>
                <strong>{selectedFile ? 'Replace STL file' : 'Click to select or drop an .stl file'}</strong>
                <span>Maximum size 25 MB</span>
              </div>
            </div>
            {selectedFile ? (
              <div className='file-summary' aria-live='polite'>
                <span className='file-name'>{selectedFile.name}</span>
                <span className='file-size'>{formatFileSize(selectedFile.size)}</span>
                <button
                  type='button'
                  className='link-button'
                  onClick={event => {
                    event.preventDefault();
                    handleRemoveFile();
                  }}
                  disabled={busy}
                >
                  Remove
                </button>
              </div>
            ) : null}
            <p className='field-hint'>Binary or ASCII .stl files up to 25 MB are supported.</p>
            {fileError ? (
              <p className='field-error' role='alert'>
                {fileError}
              </p>
            ) : null}
          </label>
          <label className='checkbox'>
            <input
              type='checkbox'
              checked={values.pauseAfterAgent1}
              onChange={event =>
                setValues(prev => ({ ...prev, pauseAfterAgent1: event.target.checked }))
              }
            />
            <span>Pause after Agent 1 completes retrieval</span>
          </label>
          <label className='checkbox'>
            <input
              type='checkbox'
              checked={values.execute}
              onChange={event => setValues(prev => ({ ...prev, execute: event.target.checked }))}
            />
            <span>Execute GenCase after config generation</span>
          </label>
          <footer className='dialog-footer'>
            <button type='button' className='ghost' onClick={onClose}>
              Cancel
            </button>
            <button type='submit' className='primary' disabled={busy}>
              {busy ? 'Triggering...' : 'Trigger run'}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
};

export default NewRunDialog;
