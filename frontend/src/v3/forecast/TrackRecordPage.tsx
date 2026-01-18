import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { AccuracyPanel } from '../../components/forecast/AccuracyPanel';
import { ApiKeysPanel } from '../../components/forecast/ApiKeysPanel';

function isLocalhost(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

function isV3ForecastTrackingEnabled(): boolean {
  // Keep prod safe (default OFF), but make localhost frictionless for dev/testing.
  return isLocalhost() || process.env.REACT_APP_V3_FORECAST_TRACKING === 'true';
}

export function TrackRecordPage(): React.ReactElement {
  const enabled = isV3ForecastTrackingEnabled();

  if (!enabled) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <Card>
          <CardHeader>
            <CardTitle>Track Record</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700 dark:text-slate-200">
            <div>WS6.1 Forecast Accountability is disabled.</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Enable with <code>REACT_APP_V3_FORECAST_TRACKING=true</code>, or run on localhost.
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Track Record</h1>
        <div className="text-sm text-slate-600 dark:text-slate-300">
          WS6.1 — forecast accountability ledger (Brier/log scoring + calibration).
        </div>
      </div>

      {/* These components expect `apiBaseUrl` to be the API prefix (usually "/api"). */}
      <AccuracyPanel apiBaseUrl="/api" />
      <ApiKeysPanel apiBaseUrl="/api" />
    </div>
  );
}

