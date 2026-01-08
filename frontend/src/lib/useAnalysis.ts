import { useState, useCallback } from 'react';

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

  const analyze = useCallback(async (input: AnalysisInput) => {
    setIsLoading(true);
    setError(null);
    try {
      // Stub implementation - Dashboard will handle actual analysis
      await new Promise(resolve => setTimeout(resolve, 100));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze');
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { analyze, data, raw, error, isLoading };
}

