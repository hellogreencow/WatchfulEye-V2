import axios from 'axios';
import type { AlertsInboxResponse, ListAlertEventsResponse } from './types';

function resolveApiBaseUrl(): string {
  const fallback = '/api';
  const raw = (process.env.REACT_APP_API_URL || '').trim();
  if (!raw) return fallback;

  const isBrowser = typeof window !== 'undefined';
  const pageHost = isBrowser ? window.location.hostname : '';
  const isLocalPage = pageHost === 'localhost' || pageHost === '127.0.0.1';

  let candidate = raw;
  try {
    if (/^https?:\/\//i.test(candidate)) {
      const u = new URL(candidate);
      const isLocalTarget = u.hostname === 'localhost' || u.hostname === '127.0.0.1';
      if (isLocalTarget && !isLocalPage) return fallback;
      if (!u.pathname || u.pathname === '/') u.pathname = '/api';
      candidate = u.toString();
    }
  } catch {
    // fall back to raw
  }

  candidate = candidate.replace(/\/$/, '');
  if (!candidate.startsWith('http') && !candidate.startsWith('/')) {
    candidate = `/${candidate}`;
  }
  return candidate;
}

const API_BASE_URL = resolveApiBaseUrl();

export async function fetchAlertEvents(limit: number): Promise<ListAlertEventsResponse> {
  const n = Math.max(1, Math.min(limit, 500));
  const url = `${API_BASE_URL}/v3/alerts/events?limit=${n}`;
  const resp = await axios.get(url, { withCredentials: true });
  return resp.data as ListAlertEventsResponse;
}

export async function fetchAlertsInbox(limit: number): Promise<AlertsInboxResponse> {
  const n = Math.max(1, Math.min(limit, 500));
  const url = `${API_BASE_URL}/v3/alerts/inbox?limit=${n}`;
  const resp = await axios.get(url, { withCredentials: true });
  return resp.data as AlertsInboxResponse;
}

export async function markAlertsSeen(lastSeenEventId: number): Promise<{ success: true; last_seen_event_id: number } | { success: false; error: string }> {
  const url = `${API_BASE_URL}/v3/alerts/inbox/mark-seen`;
  const resp = await axios.post(
    url,
    { last_seen_event_id: Math.max(0, Math.floor(lastSeenEventId || 0)) },
    { withCredentials: true }
  );
  return resp.data as any;
}


