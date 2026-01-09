import React, { useCallback, useMemo, useState } from 'react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Textarea } from '../../components/ui/textarea';
import { isExamineDisabledError, postExamine } from './api';
import type { ExamineEvidenceItem, ExamineReportContent, ExamineResponse } from './types';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is string => typeof v === 'string');
}

function looksLikeUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

function evidenceLabel(item: ExamineEvidenceItem): string {
  if (typeof item.title === 'string' && item.title.trim()) return item.title.trim();
  if (typeof item.url === 'string' && item.url.trim()) return item.url.trim();
  if (typeof item.source === 'string' && item.source.trim()) return item.source.trim();
  return 'Evidence';
}

function renderContent(content: ExamineReportContent) {
  if (content === null) {
    return <div className="text-sm text-slate-600 dark:text-slate-300">No content yet.</div>;
  }

  if (!isRecord(content)) {
    return (
      <pre className="overflow-x-auto rounded-md border bg-slate-50 p-3 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
        {String(content)}
      </pre>
    );
  }

  const bullets = toStringArray(content.bullets);
  const predictions = toStringArray(content.predictions);
  const dissent = toStringArray(content.dissent);
  const evidenceRaw = Array.isArray(content.evidence) ? content.evidence : [];

  const evidence = evidenceRaw
    .map((item) => {
      if (typeof item === 'string') return item;
      if (isRecord(item)) return item as ExamineEvidenceItem;
      return null;
    })
    .filter((x): x is string | ExamineEvidenceItem => x !== null);

  const hasStructured =
    bullets.length > 0 || predictions.length > 0 || dissent.length > 0 || evidence.length > 0;

  if (!hasStructured) {
    return (
      <pre className="overflow-x-auto rounded-md border bg-slate-50 p-3 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
        {JSON.stringify(content, null, 2)}
      </pre>
    );
  }

  return (
    <div className="space-y-6">
      {bullets.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Bullets</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-200">
            {bullets.map((b, idx) => (
              <li key={idx}>{b}</li>
            ))}
          </ul>
        </section>
      )}

      {evidence.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Evidence</h3>
          <ul className="space-y-3 text-sm">
            {evidence.map((e, idx) => {
              if (typeof e === 'string') {
                return (
                  <li key={idx} className="rounded-md border p-3 dark:border-slate-700">
                    {looksLikeUrl(e) ? (
                      <a
                        href={e}
                        target="_blank"
                        rel="noreferrer"
                        className="break-all text-blue-700 underline hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200"
                      >
                        {e}
                      </a>
                    ) : (
                      <div className="text-slate-700 dark:text-slate-200">{e}</div>
                    )}
                  </li>
                );
              }

              const url = typeof e.url === 'string' ? e.url : '';
              const title = evidenceLabel(e);
              const snippet = typeof e.snippet === 'string' ? e.snippet : '';
              const source = typeof e.source === 'string' ? e.source : '';

              return (
                <li key={idx} className="rounded-md border p-3 dark:border-slate-700">
                  <div className="flex flex-col gap-1">
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-900 underline hover:text-slate-700 dark:text-slate-50 dark:hover:text-slate-200"
                      >
                        {title}
                      </a>
                    ) : (
                      <div className="font-medium text-slate-900 dark:text-slate-50">{title}</div>
                    )}

                    {source ? (
                      <div className="text-xs text-slate-500 dark:text-slate-400">{source}</div>
                    ) : null}

                    {snippet ? (
                      <div className="text-sm text-slate-700 dark:text-slate-200">{snippet}</div>
                    ) : null}

                    {url ? (
                      <div className="break-all text-xs text-slate-500 dark:text-slate-400">{url}</div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {predictions.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Predictions</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-200">
            {predictions.map((p, idx) => (
              <li key={idx}>{p}</li>
            ))}
          </ul>
        </section>
      )}

      {dissent.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Dissent</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-200">
            {dissent.map((d, idx) => (
              <li key={idx}>{d}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function V3ExaminePage() {
  const [q, setQ] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [disabled, setDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<ExamineResponse | null>(null);

  const canSubmit = q.trim().length > 0 && !isLoading;

  const meta = useMemo(() => {
    if (!resp) return null;
    return {
      investigation_id: resp.investigation_id ?? '—',
      report_id: resp.report_id ?? '—',
      status: resp.status ?? '—',
      trace_id: resp.trace_id ?? '—',
    };
  }, [resp]);

  const onSubmit = useCallback(async () => {
    const trimmed = q.trim();
    if (!trimmed) {
      setError('Please enter a query.');
      return;
    }

    setIsLoading(true);
    setDisabled(false);
    setError(null);
    setResp(null);

    try {
      const data = await postExamine(trimmed);
      setResp(data);
    } catch (e) {
      if (isExamineDisabledError(e)) {
        setDisabled(true);
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError('Examine request failed.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [q]);

  const onClear = useCallback(() => {
    setQ('');
    setIsLoading(false);
    setDisabled(false);
    setError(null);
    setResp(null);
  }, []);

  const report = resp?.report ?? null;
  const reportTitle = report?.title ?? '';
  const reportSummary = report?.summary ?? '';
  const reportContent = report?.content ?? null;

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-6 sm:px-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
          Examine
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          V3 experimental surface (flagged). Sends{' '}
          <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs dark:bg-slate-800">
            POST /api/v3/examine
          </code>
          .
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Query</CardTitle>
          <CardDescription>
            Enter a person, org, event, or narrative to examine. Tip: press Ctrl+Enter to run.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label
              htmlFor="v3-examine-q"
              className="text-sm font-medium text-slate-700 dark:text-slate-200"
            >
              Query
            </label>
            <Textarea
              id="v3-examine-q"
              placeholder="e.g. Assess credibility of claims about X; identify key actors, evidence, and counterarguments."
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                const isSubmit = e.key === 'Enter' && (e.ctrlKey || e.metaKey);
                if (isSubmit) {
                  e.preventDefault();
                  void onSubmit();
                }
              }}
              disabled={isLoading}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void onSubmit()} disabled={!canSubmit}>
              {isLoading ? 'Examining…' : 'Examine'}
            </Button>
            <Button variant="outline" onClick={onClear} disabled={isLoading}>
              Clear
            </Button>
            {isLoading ? (
              <span className="text-sm text-slate-600 dark:text-slate-300">Working…</span>
            ) : null}
          </div>

          {disabled ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200">
              Examine is disabled.
            </div>
          ) : null}

          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200">
              {error}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Report</CardTitle>
          <CardDescription>Rendered from the API response (title, summary, content).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!resp ? (
            <div className="text-sm text-slate-600 dark:text-slate-300">
              Run an examination to see the report here.
            </div>
          ) : (
            <>
              {meta ? (
                <div className="grid gap-2 rounded-md border bg-white p-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 sm:grid-cols-2">
                  <div>
                    <span className="font-medium">investigation_id:</span>{' '}
                    <code className="break-all font-mono text-xs">{meta.investigation_id}</code>
                  </div>
                  <div>
                    <span className="font-medium">report_id:</span>{' '}
                    <code className="break-all font-mono text-xs">{meta.report_id}</code>
                  </div>
                  <div>
                    <span className="font-medium">status:</span>{' '}
                    <code className="break-all font-mono text-xs">{meta.status}</code>
                  </div>
                  <div>
                    <span className="font-medium">trace_id:</span>{' '}
                    <code className="break-all font-mono text-xs">{meta.trace_id}</code>
                  </div>
                </div>
              ) : null}

              {report ? (
                <div className="space-y-3">
                  <div className="space-y-1">
                    <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-50">
                      {reportTitle || 'Untitled report'}
                    </h2>
                    {reportSummary ? (
                      <p className="text-sm text-slate-700 dark:text-slate-200">{reportSummary}</p>
                    ) : (
                      <p className="text-sm text-slate-600 dark:text-slate-300">No summary yet.</p>
                    )}
                  </div>

                  <section className="space-y-2">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Content</h3>
                    {renderContent(reportContent)}
                  </section>
                </div>
              ) : (
                <div className="text-sm text-slate-600 dark:text-slate-300">No report returned.</div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}


