import type { RunStepStatus } from '../types/runs';
import './RunStepper.css';

interface RunStepperProps {
  steps: RunStepStatus[];
  currentStep?: string;
  onStepSelect?: (step: RunStepStatus) => void;
}

const FALLBACK_STEPS: RunStepStatus[] = [
  { step: 'reference_search', state: 'idle' },
  { step: 'config_generation', state: 'idle' },
  { step: 'execution', state: 'idle' },
];

const LABELS: Record<string, string> = {
  reference_search: 'Reference Search',
  config_generation: 'Config Generation',
  execution: 'Execution',
};

const RunStepper = ({ steps = FALLBACK_STEPS, currentStep, onStepSelect }: RunStepperProps) => {
  const normalizedSteps = steps.length > 0 ? steps : FALLBACK_STEPS;

  return (
    <ol className="run-stepper">
      {normalizedSteps.map((step, index) => {
        const label = LABELS[step.step] ?? step.step.replace(/_/g, ' ');
        const statusClass = `step-${step.state ?? 'idle'}`;
        const isActive = currentStep ? currentStep === step.step : index === 0;
        return (
          <li key={step.step} className={statusClass}>
            <button
              type="button"
              className={isActive ? 'active-step' : undefined}
              onClick={() => onStepSelect?.(step)}
            >
              <span className="step-index">{index + 1}</span>
              <span className="step-label">{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
};

export default RunStepper;
