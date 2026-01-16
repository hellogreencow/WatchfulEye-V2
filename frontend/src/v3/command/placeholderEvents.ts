export type CommandLayerId = 'conflict' | 'quakes' | 'shipping' | 'cyber' | 'markets';

export type CommandEvent = {
  id: string;
  layer: CommandLayerId;
  title: string;
  subtitle?: string;
  // ISO timestamp string
  ts: string;
  // approximate lat/lng for map placement
  lat: number;
  lng: number;
  // 1 (low) .. 5 (high)
  severity: 1 | 2 | 3 | 4 | 5;
  tags?: string[];
  // used to prefill Examine flow
  examineQuery: string;
  // optional external provenance link (placeholder)
  sourceUrl?: string;
};

function isoNowMinusMinutes(mins: number): string {
  const d = new Date(Date.now() - mins * 60_000);
  return d.toISOString();
}

// NOTE: These are intentionally PLACEHOLDER examples to stress-test UI layout,
// filtering, click behavior, and the Monitor/Examine affordances without relying
// on live connectors yet. Replace with WS5/WS9-backed layer endpoints later.
export const PLACEHOLDER_EVENTS: CommandEvent[] = [
  // Conflict (global)
  {
    id: 'conflict-001',
    layer: 'conflict',
    title: 'Localized clashes reported near Gaza City',
    subtitle: 'High signal • multiple outlets (placeholder)',
    ts: isoNowMinusMinutes(18),
    lat: 31.5017,
    lng: 34.4668,
    severity: 5,
    tags: ['conflict', 'gaza', 'idp', 'border'],
    examineQuery: 'Gaza escalation indicators last 24 hours',
    sourceUrl: 'https://example.com/placeholder/gaza',
  },
  {
    id: 'conflict-002',
    layer: 'conflict',
    title: 'Drone strike claim near Odesa',
    subtitle: 'Unverified claims (placeholder)',
    ts: isoNowMinusMinutes(44),
    lat: 46.4825,
    lng: 30.7233,
    severity: 4,
    tags: ['conflict', 'ukraine', 'drone', 'air-defense'],
    examineQuery: 'Odesa drone strike confirmation and impact',
    sourceUrl: 'https://example.com/placeholder/odesa',
  },
  {
    id: 'conflict-003',
    layer: 'conflict',
    title: 'Cross-border artillery exchange reported',
    subtitle: 'Low confidence, early reports (placeholder)',
    ts: isoNowMinusMinutes(92),
    lat: 33.8547,
    lng: 35.8623,
    severity: 3,
    tags: ['conflict', 'lebanon', 'border', 'artillery'],
    examineQuery: 'Lebanon border incident summary and evidence',
  },
  {
    id: 'conflict-004',
    layer: 'conflict',
    title: 'Protest crackdown reported in Tehran',
    subtitle: 'Civil unrest signal (placeholder)',
    ts: isoNowMinusMinutes(130),
    lat: 35.6892,
    lng: 51.389,
    severity: 3,
    tags: ['conflict', 'iran', 'unrest'],
    examineQuery: 'Tehran protest crackdown evidence and implications',
  },
  {
    id: 'conflict-005',
    layer: 'conflict',
    title: 'Militia activity reported near Port-au-Prince',
    subtitle: 'Security deterioration (placeholder)',
    ts: isoNowMinusMinutes(210),
    lat: 18.5944,
    lng: -72.3074,
    severity: 4,
    tags: ['conflict', 'haiti', 'militia', 'security'],
    examineQuery: 'Haiti security situation update',
  },

  // Quakes
  {
    id: 'quakes-001',
    layer: 'quakes',
    title: 'M5.2 quake offshore near Hokkaido',
    subtitle: 'Depth 25km (placeholder)',
    ts: isoNowMinusMinutes(23),
    lat: 42.3,
    lng: 144.2,
    severity: 3,
    tags: ['quake', 'japan', 'usgs'],
    examineQuery: 'Hokkaido earthquake supply chain risk',
  },
  {
    id: 'quakes-002',
    layer: 'quakes',
    title: 'M4.7 quake near Santiago del Estero',
    subtitle: 'Felt reports (placeholder)',
    ts: isoNowMinusMinutes(77),
    lat: -27.7833,
    lng: -64.2667,
    severity: 2,
    tags: ['quake', 'argentina'],
    examineQuery: 'Argentina quake infrastructure impact',
  },

  // Shipping / chokepoints (placeholder)
  {
    id: 'shipping-001',
    layer: 'shipping',
    title: 'Chokepoint congestion: Suez approach',
    subtitle: 'AIS density spike (placeholder)',
    ts: isoNowMinusMinutes(55),
    lat: 30.0,
    lng: 32.58,
    severity: 4,
    tags: ['shipping', 'suez', 'ais'],
    examineQuery: 'Suez congestion drivers and spillovers',
  },
  {
    id: 'shipping-002',
    layer: 'shipping',
    title: 'Red Sea rerouting trend continues',
    subtitle: 'Higher insurance premiums (placeholder)',
    ts: isoNowMinusMinutes(140),
    lat: 20.0,
    lng: 38.0,
    severity: 4,
    tags: ['shipping', 'red-sea', 'insurance'],
    examineQuery: 'Red Sea rerouting: costs and timeline',
  },

  // Cyber (placeholder)
  {
    id: 'cyber-001',
    layer: 'cyber',
    title: 'Major vendor advisory: auth bypass reported',
    subtitle: 'Patch now (placeholder)',
    ts: isoNowMinusMinutes(33),
    lat: 37.7749,
    lng: -122.4194,
    severity: 5,
    tags: ['cyber', 'advisory', 'cisa'],
    examineQuery: 'Auth bypass advisory: affected products and exploitation status',
  },
  {
    id: 'cyber-002',
    layer: 'cyber',
    title: 'Ransomware cluster activity uptick',
    subtitle: 'Healthcare targeting (placeholder)',
    ts: isoNowMinusMinutes(118),
    lat: 51.5072,
    lng: -0.1276,
    severity: 4,
    tags: ['cyber', 'ransomware', 'healthcare'],
    examineQuery: 'Ransomware wave: indicators and mitigations',
  },

  // Markets (placeholder)
  {
    id: 'markets-001',
    layer: 'markets',
    title: 'Oil spike risk: OPEC rumor mill heats up',
    subtitle: 'Volatility rising (placeholder)',
    ts: isoNowMinusMinutes(12),
    lat: 25.2048,
    lng: 55.2708,
    severity: 4,
    tags: ['markets', 'oil', 'opec'],
    examineQuery: 'Oil: OPEC cuts probability and scenarios',
  },
  {
    id: 'markets-002',
    layer: 'markets',
    title: 'FX stress: USDJPY breaks key level',
    subtitle: 'BoJ intervention watch (placeholder)',
    ts: isoNowMinusMinutes(61),
    lat: 35.6762,
    lng: 139.6503,
    severity: 3,
    tags: ['markets', 'fx', 'boj'],
    examineQuery: 'USDJPY intervention risk next 7 days',
  },
];

// Add lots of extra synthetic points to stress-test density, clustering behavior,
// and scroll performance. These are deterministic (no randomness) so tests remain stable.
export const EXTRA_PLACEHOLDER_EVENTS: CommandEvent[] = Array.from({ length: 60 }).map((_, i) => {
  const idx = i + 1;
  const layer: CommandLayerId =
    idx % 5 === 0 ? 'markets' : idx % 5 === 1 ? 'conflict' : idx % 5 === 2 ? 'quakes' : idx % 5 === 3 ? 'shipping' : 'cyber';
  const lat = -55 + (idx * 2.1) % 110; // [-55,55]
  const lng = -170 + (idx * 5.7) % 340; // [-170,170]
  const severity = ((idx % 5) + 1) as 1 | 2 | 3 | 4 | 5;
  return {
    id: `synthetic-${layer}-${String(idx).padStart(3, '0')}`,
    layer,
    title: `PLACEHOLDER ${layer.toUpperCase()} event #${idx}`,
    subtitle: 'Synthetic stress-test row (placeholder)',
    ts: isoNowMinusMinutes(10 + idx),
    lat,
    lng,
    severity,
    tags: ['placeholder', layer],
    examineQuery: `Investigate ${layer} placeholder event ${idx}`,
    sourceUrl: `https://example.com/placeholder/${layer}/${idx}`,
  };
});

