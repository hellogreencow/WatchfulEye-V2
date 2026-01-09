import { useRef, useState, useCallback } from 'react';

interface UseAnalysisOptions {
  apiBaseUrl: string;
}

interface AnalysisInput {
  title: string;
  description?: string;
  source?: string;
  category?: string;
  sentiment_score?: number;
}

export interface AnalysisStructured {
  summary?: string;
  keyPoints?: string[];
  marketImpact?: string;
  [key: string]: any;
}

interface UseAnalysisReturn {
  analyze: (input: AnalysisInput) => Promise<void>;
  data: AnalysisStructured | null;
  raw: string | null;
  error: string | null;
  isLoading: boolean;
}

export function useAnalysis({ apiBaseUrl }: UseAnalysisOptions): UseAnalysisReturn {
  const [data, setData] = useState<AnalysisStructured | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const analyze = useCallback(async (input: AnalysisInput) => {
    setIsLoading(true);
    setError(null);
    setData(null);
    setRaw(null);
    try {
      const title = (input.title || '').trim();
      const description = (input.description || '').trim();
      if (!title || !description) {
        throw new Error('Missing title/description for analysis');
      }

      // Abort any previous request
      try { abortRef.current?.abort(); } catch {}
      const controller = new AbortController();
      abortRef.current = controller;

      const endpoint = `${apiBaseUrl}/ollama-analysis`;
      const token = localStorage.getItem('auth_token');
      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(endpoint, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          title,
          description,
          source: input.source || '',
          category: input.category || '',
          sentiment_score: input.sentiment_score ?? 0,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Analysis request failed (${res.status}): ${text || res.statusText}`);
      }

      const reader = res.body?.getReader();
      if (!reader) {
        throw new Error('No response body (streaming unavailable)');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let rawText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line.startsWith('data: ')) continue;

          const payload = line.slice(6);
          if (!payload || payload === '[DONE]') continue;

          try {
            const evt = JSON.parse(payload);
            if (evt.type === 'chunk') {
              rawText += String(evt.content || '');
              setRaw(rawText);
            } else if (evt.type === 'complete') {
              rawText = String(evt.raw || rawText || '');
              setRaw(rawText);
              if (evt.structured && typeof evt.structured === 'object') {
                setData(evt.structured as AnalysisStructured);
              }
            } else if (evt.type === 'error') {
              throw new Error(String(evt.message || 'Analysis stream error'));
            }
          } catch (e) {
            // Ignore parse errors for partial chunks; only fail if it's a hard error event.
            // eslint-disable-next-line no-console
            console.warn('Failed to parse analysis SSE event', e);
          }
        }
      }
    } catch (err) {
      if ((err as any)?.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Failed to analyze');
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  return { analyze, data, raw, error, isLoading };
}

