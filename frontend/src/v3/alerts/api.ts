import axios from 'axios';
import type { ListAlertEventsResponse } from './types';

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


