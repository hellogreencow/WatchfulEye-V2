import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { PLACEHOLDER_EVENTS, EXTRA_PLACEHOLDER_EVENTS, type CommandEvent, type CommandLayerId } from './placeholderEvents';

type LayerConfig = { id: CommandLayerId; label: string };

const LAYERS: LayerConfig[] = [
  { id: 'conflict', label: 'Conflict' },
  { id: 'quakes', label: 'Quakes' },
  { id: 'shipping', label: 'Shipping' },
  { id: 'cyber', label: 'Cyber' },
  { id: 'markets', label: 'Markets' },
];

function isLocalhost(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

function isCommandCenterEnabled(): boolean {
  // Keep prod safe (default OFF), but make localhost frictionless.
  return isLocalhost() || process.env.REACT_APP_V3_COMMAND_CENTER === 'true';
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function projectEquirectangular(
  lat: number,
  lng: number,
  width: number,
  height: number
): { x: number; y: number } {
  // Equirectangular projection (placeholder). Good enough to support the core UX:
  // click hotspots → dossier → Examine/Monitor.
  const x = ((lng + 180) / 360) * width;
  const y = ((90 - lat) / 180) * height;
  return { x: clamp(x, 0, width), y: clamp(y, 0, height) };
}

function severityColor(sev: number): string {
  if (sev >= 5) return 'bg-red-500';
  if (sev >= 4) return 'bg-orange-500';
  if (sev >= 3) return 'bg-yellow-500';
  if (sev >= 2) return 'bg-emerald-500';
  return 'bg-slate-400';
}

function formatTs(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString();
}

export function CommandCenterPage(): React.ReactElement {
  const enabled = isCommandCenterEnabled();
  const [activeLayers, setActiveLayers] = useState<Record<CommandLayerId, boolean>>({
    conflict: true,
    quakes: false,
    shipping: false,
    cyber: false,
    markets: false,
  });
  const [selected, setSelected] = useState<CommandEvent | null>(null);
  const [showSynthetic, setShowSynthetic] = useState(true);
  const [examineQuery, setExamineQuery] = useState('');

  const [alertsUnread, setAlertsUnread] = useState<number | null>(null);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const [trackRecordSummary, setTrackRecordSummary] = useState<{
    total: number;
    resolved: number;
    pending: number;
  } | null>(null);
  const [trackRecordError, setTrackRecordError] = useState<string | null>(null);

  const events = useMemo(() => {
    const base = showSynthetic ? PLACEHOLDER_EVENTS.concat(EXTRA_PLACEHOLDER_EVENTS) : PLACEHOLDER_EVENTS;
    const enabledIds = new Set(
      Object.entries(activeLayers)
        .filter(([, v]) => v)
        .map(([k]) => k as CommandLayerId)
    );
    return base
      .filter((e) => enabledIds.has(e.layer))
      .sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0)); // newest first
  }, [activeLayers, showSynthetic]);

  useEffect(() => {
    if (!enabled) return;

    // LIVE: Monitor inbox unread (WS6). If WS6 is disabled or Postgres isn't configured, this will error.
    (async () => {
      try {
        setAlertsError(null);
        const res = await fetch('/api/v3/alerts/inbox?limit=1', { credentials: 'include' });
        if (res.status === 404) {
          setAlertsError('Alerts disabled (V3_ALERTS)');
          setAlertsUnread(null);
          return;
        }
        if (!res.ok) {
          const txt = await res.text();
          setAlertsError(`Inbox error (${res.status}): ${txt.slice(0, 64)}`);
          setAlertsUnread(null);
          return;
        }
        const data = await res.json();
        setAlertsUnread(typeof data?.unread_count === 'number' ? data.unread_count : Number(data?.unread_count || 0));
      } catch (e: any) {
        setAlertsError(e?.message ? String(e.message) : 'Inbox request failed');
        setAlertsUnread(null);
      }
    })();

    // LIVE: Track Record summary (WS6.1).
    (async () => {
      try {
        setTrackRecordError(null);
        const res = await fetch('/api/v3/forecast/metrics', { credentials: 'include' });
        if (res.status === 404) {
          setTrackRecordError('Forecast tracking disabled (V3_FORECAST_TRACKING)');
          setTrackRecordSummary(null);
          return;
        }
        if (!res.ok) {
          const txt = await res.text();
          setTrackRecordError(`Track Record error (${res.status}): ${txt.slice(0, 64)}`);
          setTrackRecordSummary(null);
          return;
        }
        const data = await res.json();
        const overall = data?.overall || {};
        setTrackRecordSummary({
          total: Number(overall.total_forecasts || 0),
          resolved: Number(overall.resolved_forecasts || 0),
          pending: Number(overall.pending_forecasts || 0),
        });
      } catch (e: any) {
        setTrackRecordError(e?.message ? String(e.message) : 'Track Record request failed');
        setTrackRecordSummary(null);
      }
    })();
  }, [enabled]);

  if (!enabled) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <Card>
          <CardHeader>
            <CardTitle>Command Center</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700 dark:text-slate-200">
            <div>Command Center is disabled.</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Enable with <code>REACT_APP_V3_COMMAND_CENTER=true</code>, or run on localhost.
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Layout: Top 60% map (placeholder), Bottom 40% panels. This aligns to the master plan UX baseline.
  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Command Center</h1>
          <div className="text-sm text-slate-600 dark:text-slate-300">
            Global Activity Monitor (map) + operator actions
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">Events: {events.length}</Badge>
          <Button variant="outline" onClick={() => setSelected(null)} disabled={!selected}>
            Clear selection
          </Button>
        </div>
      </div>

      {/* Operator bar: real links + real status, with explicit placeholder labeling */}
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center justify-between gap-3">
            <span>Operator</span>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">LIVE: Examine + Monitor + Track Record</Badge>
              <Badge variant="secondary">PLACEHOLDER: Map + signals</Badge>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              className="h-10 w-full rounded-md border bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              placeholder="Examine X… (e.g., 'Venezuela election unrest next 30 days')"
              value={examineQuery}
              onChange={(e) => setExamineQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const q = examineQuery.trim();
                  if (!q) return;
                  window.location.href = `/v3/examine?q=${encodeURIComponent(q)}`;
                }
              }}
            />
            <div className="flex gap-2">
              <Button
                onClick={() => {
                  const q = examineQuery.trim();
                  if (!q) return;
                  window.location.href = `/v3/examine?q=${encodeURIComponent(q)}`;
                }}
              >
                Examine
              </Button>
              <Button variant="outline" onClick={() => (window.location.href = '/monitor')}>
                Monitor
              </Button>
              <Button variant="outline" onClick={() => (window.location.href = '/v3/track')}>
                Track Record
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Card className="border-slate-200 dark:border-slate-700">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between">
                  <span>Monitor inbox</span>
                  <Badge>LIVE</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-slate-700 dark:text-slate-200">
                {alertsError ? (
                  <div className="text-xs text-slate-500 dark:text-slate-400">{alertsError}</div>
                ) : (
                  <div>
                    Unread:{' '}
                    <strong className="text-slate-900 dark:text-slate-50">
                      {alertsUnread === null ? '—' : alertsUnread}
                    </strong>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-200 dark:border-slate-700">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between">
                  <span>Track Record</span>
                  <Badge>LIVE</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-slate-700 dark:text-slate-200">
                {trackRecordError ? (
                  <div className="text-xs text-slate-500 dark:text-slate-400">{trackRecordError}</div>
                ) : (
                  <div className="space-y-1">
                    <div>
                      Tracked:{' '}
                      <strong className="text-slate-900 dark:text-slate-50">
                        {trackRecordSummary ? trackRecordSummary.total : '—'}
                      </strong>
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      Resolved {trackRecordSummary ? trackRecordSummary.resolved : '—'} · Pending{' '}
                      {trackRecordSummary ? trackRecordSummary.pending : '—'}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-200 dark:border-slate-700">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between">
                  <span>Map layers</span>
                  <Badge variant="secondary">PLACEHOLDER</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-slate-700 dark:text-slate-200">
                Toggle layers above. Next slice swaps placeholders for real connectors + citations.
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center justify-between gap-3">
            <span>Global Activity Monitor (PLACEHOLDER)</span>
            <div className="flex flex-wrap items-center gap-2">
              {LAYERS.map((l) => {
                const on = !!activeLayers[l.id];
                return (
                  <button
                    key={l.id}
                    type="button"
                    className={[
                      'rounded-md border px-2 py-1 text-xs',
                      'dark:border-slate-700',
                      on
                        ? 'border-slate-300 bg-slate-900 text-white dark:border-slate-600 dark:bg-slate-200 dark:text-slate-900'
                        : 'border-slate-200 bg-white text-slate-700 dark:bg-slate-950 dark:text-slate-200',
                    ].join(' ')}
                    onClick={() =>
                      setActiveLayers((prev) => ({
                        ...prev,
                        [l.id]: !prev[l.id],
                      }))
                    }
                    aria-pressed={on}
                  >
                    {l.label}
                  </button>
                );
              })}
              <label className="ml-2 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={showSynthetic}
                  onChange={(e) => setShowSynthetic(e.target.checked)}
                />
                Extra placeholders
              </label>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-xs text-slate-500 dark:text-slate-400">
            PLACEHOLDER map projection + placeholder events. Next slice replaces these with WS5/WS9-backed real
            connectors + citations.
          </div>

          <div className="relative h-[420px] w-full overflow-hidden rounded-md border bg-gradient-to-b from-slate-50 to-slate-100 dark:border-slate-700 dark:from-slate-950 dark:to-slate-900">
            {/* faux grid background (command-center vibe, no external map deps) */}
            <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:linear-gradient(to_right,rgba(15,23,42,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.08)_1px,transparent_1px)] [background-size:48px_48px] dark:opacity-30 dark:[background-image:linear-gradient(to_right,rgba(148,163,184,0.12)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.12)_1px,transparent_1px)]" />

            {/* markers */}
            <div className="absolute inset-0">
              {events.map((e) => {
                const { x, y } = projectEquirectangular(e.lat, e.lng, 1000, 420);
                const leftPct = (x / 1000) * 100;
                const topPct = (y / 420) * 100;
                const selectedNow = selected?.id === e.id;
                return (
                  <button
                    key={e.id}
                    type="button"
                    className={[
                      'absolute -translate-x-1/2 -translate-y-1/2 rounded-full border',
                      'shadow-sm',
                      selectedNow ? 'scale-125 border-white ring-2 ring-slate-900 dark:ring-slate-100' : 'border-white/60',
                      severityColor(e.severity),
                    ].join(' ')}
                    style={{ left: `${leftPct}%`, top: `${topPct}%`, width: 10 + e.severity * 2, height: 10 + e.severity * 2 }}
                    title={`${e.title} (${e.layer})`}
                    onClick={() => setSelected(e)}
                  />
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
        <Card className="md:col-span-5">
          <CardHeader>
            <CardTitle>Selected</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!selected ? (
              <div className="text-sm text-slate-600 dark:text-slate-300">
                Click a hotspot on the map to open a mini dossier.
              </div>
            ) : (
              <>
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{selected.layer}</Badge>
                    <Badge variant="secondary">sev {selected.severity}</Badge>
                  </div>
                  <div className="text-sm font-semibold text-slate-900 dark:text-slate-50">{selected.title}</div>
                  {selected.subtitle && (
                    <div className="text-xs text-slate-600 dark:text-slate-300">{selected.subtitle}</div>
                  )}
                  <div className="text-xs text-slate-500 dark:text-slate-400">{formatTs(selected.ts)}</div>
                </div>

                {selected.tags && selected.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {selected.tags.slice(0, 8).map((t) => (
                      <span
                        key={t}
                        className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  <Button
                    onClick={() => {
                      const q = encodeURIComponent(selected.examineQuery);
                      window.location.href = `/v3/examine?q=${q}`;
                    }}
                  >
                    Examine
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      // For now, Monitor action takes you to the inbox view where alerts land.
                      // Next slice will create a real alert rule from this selection.
                      window.location.href = `/monitor`;
                    }}
                  >
                    Monitor
                  </Button>
                </div>

                {selected.sourceUrl && (
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    source (placeholder): <a className="underline" href={selected.sourceUrl} target="_blank" rel="noreferrer">{selected.sourceUrl}</a>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card className="md:col-span-7">
          <CardHeader>
            <CardTitle>Recent signals (PLACEHOLDER)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {events.slice(0, 20).map((e) => (
              <button
                key={`row-${e.id}`}
                type="button"
                className={[
                  'w-full rounded-md border p-3 text-left',
                  'hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900',
                  selected?.id === e.id ? 'border-slate-400 dark:border-slate-500' : 'border-slate-200',
                ].join(' ')}
                onClick={() => setSelected(e)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`inline-block h-2.5 w-2.5 rounded-full ${severityColor(e.severity)}`} />
                      <Badge variant="secondary">{e.layer}</Badge>
                      <span className="truncate text-sm font-medium text-slate-900 dark:text-slate-50">
                        {e.title}
                      </span>
                    </div>
                    {e.subtitle && (
                      <div className="mt-1 truncate text-xs text-slate-600 dark:text-slate-300">{e.subtitle}</div>
                    )}
                  </div>
                  <div className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{formatTs(e.ts)}</div>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

