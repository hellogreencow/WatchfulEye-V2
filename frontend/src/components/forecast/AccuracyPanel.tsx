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

interface ForecastMetrics {
  overall: {
    total_forecasts: number;
    mean_brier_score: number | null;
    calibration_error: number | null;
    accuracy_percentage: number | null;
    hit_rate_by_horizon?: {
      '7_days': number | null;
      '30_days': number | null;
      '90_days': number | null;
    };
  };
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

export function AccuracyPanel() {
  const [metrics, setMetrics] = useState<ForecastMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    try {
      const response = await fetch('/api/v3/forecast/metrics');
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

  const { overall, by_domain, recent_performance, calibration_curve } = metrics;

  // Calculate accuracy grade
  const getAccuracyGrade = (brierScore: number | null): string => {
    if (brierScore === null) return 'N/A';
    if (brierScore < 0.15) return 'A+';
    if (brierScore < 0.20) return 'A';
    if (brierScore < 0.25) return 'B';
    if (brierScore < 0.30) return 'C';
    return 'D';
  };

  const getGradeColor = (grade: string): string => {
    if (grade === 'A+' || grade === 'A') return 'text-green-400';
    if (grade === 'B') return 'text-yellow-400';
    if (grade === 'C') return 'text-orange-400';
    return 'text-red-400';
  };

  const grade = getAccuracyGrade(overall.mean_brier_score);
  const gradeColor = getGradeColor(grade);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Track Record</h2>
        <div className="text-sm text-gray-400">
          {overall.total_forecasts} forecasts tracked
        </div>
      </div>

      {/* Overall Accuracy Card */}
      <Card className="p-6 bg-gradient-to-br from-gray-900 to-gray-800 border-gray-700">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {/* Accuracy Grade */}
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-2">Accuracy Grade</div>
            <div className={`text-4xl font-bold ${gradeColor}`}>{grade}</div>
            <div className="text-xs text-gray-500 mt-1">
              Brier: {overall.mean_brier_score?.toFixed(3) || 'N/A'}
            </div>
          </div>

          {/* Hit Rate */}
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-2">Hit Rate</div>
            <div className="text-4xl font-bold text-blue-400">
              {overall.accuracy_percentage?.toFixed(0) || '—'}
              {overall.accuracy_percentage !== null && '%'}
            </div>
            <div className="text-xs text-gray-500 mt-1">Binary accuracy</div>
          </div>

          {/* Calibration */}
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-2">Calibration</div>
            <div className="text-4xl font-bold text-purple-400">
              {overall.calibration_error !== null
                ? (overall.calibration_error * 100).toFixed(1)
                : '—'}
              {overall.calibration_error !== null && '%'}
            </div>
            <div className="text-xs text-gray-500 mt-1">Mean error</div>
          </div>

          {/* 30-Day Hit Rate */}
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-2">30-Day Accuracy</div>
            <div className="text-4xl font-bold text-cyan-400">
              {overall.hit_rate_by_horizon?.['30_days'] !== null &&
              overall.hit_rate_by_horizon?.['30_days'] !== undefined
                ? (overall.hit_rate_by_horizon['30_days'] * 100).toFixed(0)
                : '—'}
              {overall.hit_rate_by_horizon?.['30_days'] !== null &&
                overall.hit_rate_by_horizon?.['30_days'] !== undefined &&
                '%'}
            </div>
            <div className="text-xs text-gray-500 mt-1">Short-term</div>
          </div>
        </div>
      </Card>

      {/* By-Domain Performance */}
      {Object.keys(by_domain).length > 0 && (
        <Card className="p-6 bg-gray-900/50 border-gray-800">
          <h3 className="text-lg font-semibold text-white mb-4">Performance by Domain</h3>
          <div className="space-y-3">
            {Object.entries(by_domain).map(([domain, data]) => {
              const domainGrade = getAccuracyGrade(data.avg_brier);
              const domainColor = getGradeColor(domainGrade);
              return (
                <div key={domain} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`font-bold ${domainColor}`}>{domainGrade}</div>
                    <div className="text-white capitalize">{domain}</div>
                    <div className="text-sm text-gray-500">({data.count} forecasts)</div>
                  </div>
                  <div className="text-sm text-gray-400">
                    Brier: {data.avg_brier.toFixed(3)}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Recent Performance Trend */}
      {recent_performance.length > 0 && (
        <Card className="p-6 bg-gray-900/50 border-gray-800">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Performance (30 Days)</h3>
          <div className="space-y-2">
            {recent_performance.slice(-7).map((day) => (
              <div key={day.date} className="flex items-center justify-between text-sm">
                <div className="text-gray-400">{day.date}</div>
                <div className="flex items-center gap-4">
                  <div className="text-gray-500">{day.count} forecasts</div>
                  <div className={getGradeColor(getAccuracyGrade(day.brier))}>
                    Brier: {day.brier.toFixed(3)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Calibration Curve */}
      {Object.keys(calibration_curve).length > 0 && (
        <Card className="p-6 bg-gray-900/50 border-gray-800">
          <h3 className="text-lg font-semibold text-white mb-4">Calibration Curve</h3>
          <div className="text-sm text-gray-400 mb-4">
            Perfect calibration: forecasts at 70% should happen 70% of the time
          </div>
          <div className="space-y-2">
            {Object.entries(calibration_curve)
              .sort(([a], [b]) => parseInt(a) - parseInt(b))
              .map(([bin, data]) => {
                const binMid = (parseInt(bin) + 0.5) * 10;
                const isWellCalibrated = data.error < 0.10;
                return (
                  <div key={bin} className="flex items-center gap-3">
                    <div className="text-gray-500 w-12">{binMid}%</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {/* Expected bar */}
                        <div className="flex-1 bg-gray-700 rounded-full h-2 relative overflow-hidden">
                          <div
                            className="absolute h-full bg-blue-500/30"
                            style={{ width: `${data.expected * 100}%` }}
                          ></div>
                          {/* Observed bar */}
                          <div
                            className={`absolute h-full ${
                              isWellCalibrated ? 'bg-green-500' : 'bg-yellow-500'
                            }`}
                            style={{ width: `${data.observed * 100}%` }}
                          ></div>
                        </div>
                        <div className="text-xs text-gray-400 w-20">
                          {(data.observed * 100).toFixed(0)}% ({data.count})
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
          <div className="mt-4 text-xs text-gray-500">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500/30 rounded"></div>
                <span>Expected</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded"></div>
                <span>Observed (well-calibrated)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded"></div>
                <span>Observed (needs adjustment)</span>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Methodology Note */}
      <Card className="p-4 bg-gray-900/30 border-gray-800">
        <div className="text-xs text-gray-500">
          <strong className="text-gray-400">Methodology:</strong> Accuracy measured using Brier
          score (proper scoring rule). Target: Brier &lt;0.20 (A grade), calibration error &lt;0.10.
          Based on research by Tetlock et al. (Superforecasting) and Mellers et al. (2014).
        </div>
      </Card>
    </div>
  );
}
