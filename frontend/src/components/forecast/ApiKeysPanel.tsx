/**
 * WS6.1: Admin API keys + endpoint test panel.
 *
 * Goal: Configure connector credentials and quickly verify connectivity from the UI.
 * Security: Backend endpoints are admin-only + V3_FORECAST_TRACKING-gated.
 *
 * Backend:
 * - GET  /api/v3/admin/api-keys
 * - PUT  /api/v3/admin/api-keys/:name
 * - POST /api/v3/admin/api-keys/:name/test
 * - POST /api/v3/admin/endpoints/test
 */

import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

type ApiKeyStatus = {
  name: string;
  label: string;
  env_var?: string | null;
  env_configured: boolean;
  stored_configured: boolean;
  configured: boolean;
  updated_at?: string | null;
  updated_by?: string | null;
  docs?: string | null;
};

type EndpointTest = {
  id: string;
  label: string;
  docs?: string | null;
};

type ApiKeysResponse = {
  encryption_configured: boolean;
  keys: ApiKeyStatus[];
  endpoint_tests: EndpointTest[];
};

type TestResult =
  | { ok: true; message: string; [k: string]: any }
  | { ok: false; error: string; [k: string]: any };

export function ApiKeysPanel({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ApiKeysResponse | null>(null);

  const [alphaKey, setAlphaKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, TestResult | null>>({});

  const api = useMemo(() => {
    const base = (apiBaseUrl || '').replace(/\/$/, '');
    return {
      list: `${base}/v3/admin/api-keys`,
      setKey: (name: string) => `${base}/v3/admin/api-keys/${encodeURIComponent(name)}`,
      testKey: (name: string) => `${base}/v3/admin/api-keys/${encodeURIComponent(name)}/test`,
      testEndpoint: `${base}/v3/admin/endpoints/test`,
    };
  }, [apiBaseUrl]);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(api.list);
      setData(res.data);
    } catch (e: any) {
      const msg =
        e?.response?.status === 404
          ? 'WS6.1 disabled (V3_FORECAST_TRACKING=false)'
          : e?.response?.data?.error || e?.message || 'Failed to load API key status';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveAlphaVantage = async () => {
    setSaving(true);
    setError(null);
    try {
      await axios.put(api.setKey('alpha_vantage'), { value: alphaKey });
      setAlphaKey('');
      await refresh();
    } catch (e: any) {
      setError(e?.response?.data?.error || e?.message || 'Failed to save key');
    } finally {
      setSaving(false);
    }
  };

  const runTest = async (id: string) => {
    setTestResults((prev) => ({ ...prev, [id]: null }));
    try {
      const res =
        id === 'alpha_vantage'
          ? await axios.post(api.testKey('alpha_vantage'), {})
          : await axios.post(api.testEndpoint, { endpoint: id });
      setTestResults((prev) => ({ ...prev, [id]: res.data }));
    } catch (e: any) {
      setTestResults((prev) => ({
        ...prev,
        [id]: { ok: false, error: e?.response?.data?.error || e?.message || 'Test failed' },
      }));
    }
  };

  return (
    <Card className="p-6 bg-gray-900/50 border-gray-800 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-white">Integrations: API Keys & Connectivity</div>
          <div className="text-xs text-gray-400">
            Admin-only. Stored keys are encrypted at rest in Postgres.
          </div>
        </div>
        <Button variant="secondary" onClick={refresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {error && <div className="text-sm text-red-400">{error}</div>}

      {!data ? (
        <div className="text-sm text-gray-400">{loading ? 'Loading…' : 'No data'}</div>
      ) : (
        <div className="space-y-6">
          <div className="text-xs text-gray-400">
            Encryption configured:{' '}
            <span className={data.encryption_configured ? 'text-green-400' : 'text-red-400'}>
              {data.encryption_configured ? 'YES' : 'NO'}
            </span>
          </div>

          {/* Key: Alpha Vantage */}
          <div className="rounded border border-gray-800 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-white">Alpha Vantage</div>
                <div className="text-xs text-gray-500">Used for markets fallback when Yahoo is blocked.</div>
              </div>
              <Button onClick={() => runTest('alpha_vantage')} variant="outline">
                Test
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-gray-400">
              {(() => {
                const s = data.keys.find((k) => k.name === 'alpha_vantage');
                if (!s) return null;
                return (
                  <>
                    <div>
                      env: <span className={s.env_configured ? 'text-green-400' : 'text-gray-500'}>{s.env_configured ? 'set' : 'unset'}</span>
                    </div>
                    <div>
                      stored: <span className={s.stored_configured ? 'text-green-400' : 'text-gray-500'}>{s.stored_configured ? 'set' : 'unset'}</span>
                    </div>
                    <div>
                      effective:{' '}
                      <span className={s.configured ? 'text-green-400' : 'text-red-400'}>
                        {s.configured ? 'configured' : 'missing'}
                      </span>
                    </div>
                  </>
                );
              })()}
            </div>

            <div className="flex flex-col md:flex-row gap-2">
              <Input
                type="password"
                placeholder="Enter Alpha Vantage API key"
                value={alphaKey}
                onChange={(e) => setAlphaKey(e.target.value)}
              />
              <Button onClick={saveAlphaVantage} disabled={saving || alphaKey.trim().length === 0}>
                {saving ? 'Saving…' : 'Save'}
              </Button>
            </div>

            {testResults['alpha_vantage'] && (
              <div className="text-xs">
                {testResults['alpha_vantage']?.ok ? (
                  <span className="text-green-400">{testResults['alpha_vantage']?.message || 'OK'}</span>
                ) : (
                  <span className="text-red-400">{testResults['alpha_vantage']?.error || 'FAILED'}</span>
                )}
              </div>
            )}
          </div>

          {/* Endpoint tests */}
          <div className="rounded border border-gray-800 p-4 space-y-3">
            <div className="text-sm font-semibold text-white">Endpoint Tests (no key required)</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {data.endpoint_tests.map((t) => (
                <div key={t.id} className="border border-gray-800 rounded p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-white">{t.label}</div>
                    <Button onClick={() => runTest(t.id)} variant="outline" size="sm">
                      Test
                    </Button>
                  </div>
                  {testResults[t.id] && (
                    <div className="text-xs">
                      {testResults[t.id]?.ok ? (
                        <span className="text-green-400">{testResults[t.id]?.message || 'OK'}</span>
                      ) : (
                        <span className="text-red-400">{testResults[t.id]?.error || 'FAILED'}</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}


