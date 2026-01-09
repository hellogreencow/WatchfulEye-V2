import type { ExamineRequest, ExamineResponse } from './types';

export class ExamineDisabledError extends Error {
  readonly code = 'disabled' as const;

  constructor(message = 'Examine is disabled') {
    super(message);
    this.name = 'ExamineDisabledError';
  }
}

export function isExamineDisabledError(err: unknown): err is ExamineDisabledError {
  if (err instanceof ExamineDisabledError) return true;
  if (typeof err !== 'object' || err === null) return false;
  return (err as { code?: unknown }).code === 'disabled';
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function postExamine(q: string): Promise<ExamineResponse> {
  const payload: ExamineRequest = { q };

  const res = await fetch('/api/v3/examine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  // Backend flag off (or route not present) should not crash the UI.
  if (res.status === 404) {
    throw new ExamineDisabledError();
  }

  const text = await res.text();
  const json = text ? safeJsonParse(text) : null;

  if (!res.ok) {
    let detail = '';
    if (json && typeof json === 'object' && 'error' in json) {
      const maybeError = (json as { error?: unknown }).error;
      if (typeof maybeError === 'string') detail = maybeError;
    }
    const msg = detail
      ? `Examine request failed (${res.status}): ${detail}`
      : `Examine request failed (${res.status})`;
    throw new Error(msg);
  }

  // If JSON parsing fails but res.ok is true, still return a safe empty object.
  return (json ?? {}) as ExamineResponse;
}


