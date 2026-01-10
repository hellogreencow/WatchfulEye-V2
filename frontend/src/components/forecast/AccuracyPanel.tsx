/**
 * WS6.1 TASK 7: AccuracyPanel - Track Record Display
 *
 * Displays forecast accountability metrics:
 * - Overall accuracy (Brier score, calibration)
 * - By-domain performance (geopolitics, markets, cyber)
 * - Recent performance trends
 * - Calibration curve visualization
 *
 * Data source: GET /api/v3/forecast/metrics
 */

import React, { useEffect, useState } from 'react';
import { Card } from '../ui/card';

interface RecentForecast {
  id: string;
  claim: string;
  probability: number;
  horizon_days: number;
  horizon_date: string | null;
  outcome_status: string;
  outcome_result: boolean | null;
  brier_score: number | null;
  log_score: number | null;
  outcome_method: string | null;
  outcome_measured_at: string | null;
  created_at: string | null;
  tags?: string[];
}

interface ForecastMetrics {
  overall: {
    total_forecasts: number;
    resolved_forecasts: number;
    pending_forecasts: number;
    unresolved_forecasts?: number;
    invalid_forecasts?: number;
    mean_brier_score: number | null;
    mean_log_score: number | null;
    calibration_error: number | null;
    accuracy_percentage: number | null;
    hit_rate_by_horizon?: {
      '7_days': number | null;
      '30_days': number | null;
      '90_days': number | null;
    };
  };
  guardrails?: {
    min_resolved_for_grade: number;
    min_resolved_for_calibration: number;
    min_resolved_for_domain: number;
  };
  recent_forecasts?: RecentForecast[];
  by_domain: {
    [domain: string]: {
      avg_brier: number;
      count: number;
    };
  };
  recent_performance: Array<{
    date: string;
    brier: number;
    count: number;
  }>;
  calibration_curve: {
    [bin: string]: {
      expected: number;
      observed: number;
      count: number;
      error: number;
    };
  };
}

export function AccuracyPanel({ apiBaseUrl }: { apiBaseUrl?: string }) {
  const [metrics, setMetrics] = useState<ForecastMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const base = (apiBaseUrl || '').replace(/\/+$/, '');
        const response = await fetch(`${base}/api/v3/forecast/metrics`);
        if (response.status === 404) {
          // Feature not enabled
          setError('Forecast tracking not enabled');
          setLoading(false);
          return;
        }
        if (!response.ok) {
          throw new Error(`Failed to fetch metrics: ${response.statusText}`);
        }
        const data = await response.json();
        setMetrics(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load metrics');
      } finally {
        setLoading(false);
      }
    };
    fetchMetrics();
  }, [apiBaseUrl]);

  if (loading) {
    return (
      <Card className="p-6 bg-gray-900/50 border-gray-800">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-800 rounded w-1/3"></div>
          <div className="h-32 bg-gray-800 rounded"></div>
        </div>
      </Card>
    );
  }

  if (error || !metrics) {
    return (
      <Card className="p-6 bg-gray-900/50 border-gray-800">
        <div className="text-gray-400 text-center">
          {error || 'No forecast data available'}
        </div>
      </Card>
    );
  }

  const { overall } = metrics;
  const recent = metrics.recent_forecasts || [];

  const resolved = overall.resolved_forecasts ?? 0;
  const pending = overall.pending_forecasts ?? 0;
  const unresolved = overall.unresolved_forecasts ?? 0;
  const invalid = overall.invalid_forecasts ?? 0;
  const total = overall.total_forecasts ?? 0;

  const guardrails = metrics.guardrails || {
    min_resolved_for_grade: 20,
    min_resolved_for_calibration: 50,
    min_resolved_for_domain: 10,
  };

  const verdictLabel = (f: RecentForecast): { label: string; className: string } => {
    if (f.outcome_status === 'resolved') {
      return f.outcome_result
        ? { label: 'Supported', className: 'text-green-400' }
        : { label: 'Refuted', className: 'text-red-400' };
    }
    if (f.outcome_status === 'pending') return { label: 'Pending', className: 'text-yellow-400' };
    if (f.outcome_status === 'unresolved') return { label: 'Unresolved', className: 'text-orange-400' };
    if (f.outcome_status === 'invalid') return { label: 'Unverifiable', className: 'text-gray-400' };
    return { label: f.outcome_status, className: 'text-gray-400' };
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Accountability Ledger</h2>
        <div className="text-sm text-gray-400">
          {total} items tracked
        </div>
      </div>

      {/* Summary counters */}
      <Card className="p-6 bg-gray-900/50 border-gray-800">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-sm text-gray-400">Resolved</div>
            <div className="text-3xl font-bold text-white">{resolved}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-400">Pending</div>
            <div className="text-3xl font-bold text-yellow-400">{pending}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-400">Unresolved</div>
            <div className="text-3xl font-bold text-orange-400">{unresolved}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-400">Unverifiable</div>
            <div className="text-3xl font-bold text-gray-300">{invalid}</div>
          </div>
        </div>

        <div className="mt-4 text-sm text-gray-400">
          {resolved < guardrails.min_resolved_for_grade ? (
            <div>
              Not enough resolved items to show grades/charts yet. Need{' '}
              <strong className="text-gray-200">{guardrails.min_resolved_for_grade}</strong> resolved
              (currently {resolved}).
            </div>
          ) : (
            <div>
              Mean Brier: <strong className="text-gray-200">{overall.mean_brier_score?.toFixed(3)}</strong>{' '}
              · Accuracy: <strong className="text-gray-200">{overall.accuracy_percentage?.toFixed(0)}%</strong>
            </div>
          )}
        </div>
      </Card>

      {/* Ledger */}
      <Card className="p-6 bg-gray-900/50 border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Recent items</h3>
          <button
            className="text-sm text-gray-400 hover:text-gray-200"
            onClick={() => setShowAdvanced((v) => !v)}
            type="button"
          >
            {showAdvanced ? 'Hide' : 'Show'} advanced metrics
          </button>
        </div>

        {recent.length === 0 ? (
          <div className="text-gray-400">No items yet.</div>
        ) : (
          <div className="space-y-3">
            {recent.slice(0, 10).map((f) => {
              const v = verdictLabel(f);
              return (
                <div key={f.id} className="rounded border border-gray-800 bg-gray-950/30 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className={`text-xs font-semibold ${v.className}`}>{v.label}</div>
                      <div className="text-sm text-white truncate">{f.claim}</div>
                      <div className="mt-1 text-xs text-gray-400">
                        p={f.probability} · {f.horizon_days}d · method={f.outcome_method || '—'}
                        {f.outcome_measured_at ? ` · measured=${f.outcome_measured_at}` : ''}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Brier</div>
                      <div className="text-sm text-gray-200">
                        {f.brier_score !== null && f.brier_score !== undefined
                          ? Number(f.brier_score).toFixed(3)
                          : '—'}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Advanced metrics (progressive disclosure) */}
      {showAdvanced && (
        <Card className="p-6 bg-gray-900/30 border-gray-800">
          <div className="text-sm text-gray-400 space-y-2">
            <div>
              <strong className="text-gray-200">Mean Brier:</strong>{' '}
              {overall.mean_brier_score !== null ? overall.mean_brier_score.toFixed(4) : '—'}
            </div>
            <div>
              <strong className="text-gray-200">Calibration error:</strong>{' '}
              {overall.calibration_error !== null ? (overall.calibration_error * 100).toFixed(1) + '%' : '—'}
              <span className="text-gray-500"> (hidden unless enough data)</span>
            </div>
            <div>
              <strong className="text-gray-200">Mean log score:</strong>{' '}
              {overall.mean_log_score !== null ? overall.mean_log_score.toFixed(4) : '—'}
            </div>
          </div>
        </Card>
      )}

      {/* Methodology Note */}
      <Card className="p-4 bg-gray-900/30 border-gray-800">
        <div className="text-xs text-gray-500">
          <strong className="text-gray-400">Methodology:</strong> For resolved forecasts, we score with Brier/log
          (proper scoring rules). We hide grades/calibration until sample sizes are large enough to be honest.
        </div>
      </Card>
    </div>
  );
}
