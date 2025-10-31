export const MODEL_OPTIONS = [
  'gpt-5-mini',
  'gpt-5-nano',
  'gpt-5',
] as const;

export type ModelOption = (typeof MODEL_OPTIONS)[number];

export const DEFAULT_MODEL: ModelOption = MODEL_OPTIONS[0];
