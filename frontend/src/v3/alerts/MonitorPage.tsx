import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { fetchAlertsInbox, markAlertsSeen } from './api';
import type { AlertEventRow } from './types';

function isLocalhost(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

function canShowAlertsUI(): boolean {
  // Keep prod safe (default OFF), but make localhost frictionless.
  return isLocalhost() || process.env.REACT_APP_V3_ALERTS === 'true';
}

function asJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function shortType(event: AlertEventRow): string {
  const rt = (event.rule_type || '').trim();
  if (rt) return rt;
  return (event.event_type || 'event').trim() || 'event';
}

export function MonitorPage(): React.ReactElement {
  const enabled = canShowAlertsUI();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<AlertEventRow[]>([]);
  const [limit, setLimit] = useState(100);
  const [expandedId, setExpandedId] = useState<string | number | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [lastSeenId, setLastSeenId] = useState(0);
  const [newestId, setNewestId] = useState(0);

  const sorted = useMemo(() => {
    // API already returns newest first; keep stable.
    return events;
  }, [events]);

  async function refresh(): Promise<void> {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAlertsInbox(limit);
      if (!res || res.success !== true) {
        const msg = (res as any)?.error || 'Failed to load alert events';
        setError(String(msg));
        setEvents([]);
        setUnreadCount(0);
        return;
      }
      setEvents(res.data || []);
      setUnreadCount(Number((res as any).unread_count || 0));
      setLastSeenId(Number((res as any).last_seen_event_id || 0));
      setNewestId(Number((res as any).newest_event_id || 0));
    } catch (e: any) {
      const status = e?.response?.status;
      if (status === 404) setError('Alerts are disabled on the server (V3_ALERTS).');
      else if (status === 401) setError('Login required.');
      else if (status === 403) setError('Admin access required.');
      else setError(e?.message ? String(e.message) : 'Request failed');
      setEvents([]);
      setUnreadCount(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limit, enabled]);

  if (!enabled) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Card>
          <CardHeader>
            <CardTitle>Monitor</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700 dark:text-slate-200">
            <div>Alerts UI is disabled.</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Enable with <code>REACT_APP_V3_ALERTS=true</code>, or run on localhost.
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Monitor</h1>
          <div className="text-sm text-slate-600 dark:text-slate-300">
            Recent alert events (in-app inbox)
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={unreadCount > 0 ? 'default' : 'secondary'}>Unread: {unreadCount}</Badge>
          <Button
            onClick={async () => {
              try {
                const target = newestId || lastSeenId;
                if (!target) return;
                const res = await markAlertsSeen(target);
                if ((res as any)?.success === true) {
                  setLastSeenId(Number((res as any).last_seen_event_id || target));
                  await refresh();
                } else {
                  setError(String((res as any)?.error || 'Failed to mark seen'));
                }
              } catch (e: any) {
                setError(e?.message ? String(e.message) : 'Failed to mark seen');
              }
            }}
            disabled={loading || newestId <= 0 || newestId <= lastSeenId}
            variant="outline"
          >
            Mark seen
          </Button>
          <select
            className="h-9 rounded-md border bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            <option value={50}>Last 50</option>
            <option value={100}>Last 100</option>
            <option value={200}>Last 200</option>
            <option value={500}>Last 500</option>
          </select>
          <Button onClick={() => void refresh()} disabled={loading} variant="outline">
            {loading ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
      </div>

      {error && (
        <Card>
          <CardContent className="p-4 text-sm text-red-700 dark:text-red-300">{error}</CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Events <Badge variant="secondary">{sorted.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {sorted.length === 0 && !error && (
            <div className="text-sm text-slate-600 dark:text-slate-300">
              No events yet. Create an alert rule and run the evaluator job.
            </div>
          )}

          {sorted.map((ev) => {
            const isExpanded = expandedId === ev.id;
            return (
              <div key={String(ev.id)} className="rounded-md border p-3 dark:border-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{shortType(ev)}</Badge>
                      {ev.rule_name && (
                        <span className="truncate text-sm font-medium text-slate-900 dark:text-slate-50">
                          {ev.rule_name}
                        </span>
                      )}
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {ev.created_at}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                      rule_id: <code>{ev.rule_id}</code>
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setExpandedId(isExpanded ? null : ev.id)}
                  >
                    {isExpanded ? 'Hide' : 'View'}
                  </Button>
                </div>

                {isExpanded && (
                  <pre className="mt-3 overflow-x-auto rounded-md border bg-slate-50 p-3 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
                    {asJson(ev.payload)}
                  </pre>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}


