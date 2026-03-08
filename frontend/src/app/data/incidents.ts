/**
 * RoadSense AI — API Service (src/data/incidents.ts)
 * Drop-in replacement for the mock data file.
 * Fetches real incidents from the Insights API and maps them to the Incident interface.
 *
 * Setup: create a .env file in the frontend root with:
 *   VITE_API_URL=https://rrtwy6f3hk.execute-api.us-east-1.amazonaws.com/prod
 */

const API_URL = import.meta.env.VITE_API_URL || "";

// ── Incident interface — unchanged from original ──────────────────────────────

export interface Incident {
  id: string;
  code: string;
  confidence: number;
  origin: string;
  damageType: string;
  damageAbbrev: string;
  severity: 'LOW' | 'MED' | 'HIGH' | 'CRIT';
  severityColor: string;
  signalsDetected: number;
  lastUpdated: string;
  timestamp: number;
  languages: { flag: string; name: string; count: number }[];
  sources: { name: string; count: number }[];
  summary: string;
  explanation: string;
  lat: number;
  lng: number;
  status: 'active' | 'under_verification' | 'solved';
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const SEVERITY_MAP: Record<string, 'LOW' | 'MED' | 'HIGH' | 'CRIT'> = {
  critical: 'CRIT',
  high:     'HIGH',
  medium:   'MED',
  low:      'LOW',
};

const SEVERITY_COLORS: Record<string, string> = {
  CRIT: '#ef4444',
  HIGH: '#f97316',
  MED:  '#fbbf24',
  LOW:  '#fef3c7',
};

const DAMAGE_ABBREV: Record<string, string> = {
  Pothole:      'POT',
  'Road Damage': 'DMG',
  Flooding:     'FLD',
  'Surface Wear': 'SRF',
  general:      'GEN',
};

// ── API → Incident adapter ────────────────────────────────────────────────────

function adaptIncident(raw: Record<string, any>): Incident {
  const severity = SEVERITY_MAP[raw.severity?.toLowerCase()] ?? 'LOW';
  const damageType = raw.damageType ?? 'Road Damage';
  const updatedAt = raw.updatedAt || raw.createdAt || new Date().toISOString();

  return {
    id:              raw.id,
    code:            raw.code,
    confidence:      raw.confidence ?? 0,
    origin:          raw.origin ?? 'Unknown',
    damageType:      damageType,
    damageAbbrev:    DAMAGE_ABBREV[damageType] ?? 'DMG',
    severity:        severity,
    severityColor:   SEVERITY_COLORS[severity],
    signalsDetected: raw.signalCount ?? raw.signalsDetected ?? 0,
    lastUpdated:     timeAgo(updatedAt),
    timestamp:       new Date(raw.createdAt || updatedAt).getTime(),
    languages:       raw.languages ?? [],
    sources:         raw.sources ?? [],
    summary:         raw.summary ?? '',
    explanation:     raw.summary ?? '',   // API returns explanation in summary field
    lat:             raw.lat ?? 12.9716,
    lng:             raw.lng ?? 77.5946,
    status:          raw.status === 'resolved' ? 'solved'
                   : raw.status === 'under_verification' ? 'under_verification'
                   : 'active',
  };
}

// ── API calls ─────────────────────────────────────────────────────────────────

export async function fetchIncidents(): Promise<Incident[]> {
  if (!API_URL) {
    console.warn('[RoadSense] VITE_API_URL not set — using mock data');
    return mockIncidents;
  }
  try {
    const res = await fetch(`${API_URL}/incidents`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    return (data.incidents ?? []).map(adaptIncident);
  } catch (e) {
    console.error('[RoadSense] fetchIncidents failed:', e);
    return mockIncidents;
  }
}

export async function fetchIncidentById(id: string): Promise<Incident | null> {
  if (!API_URL) return mockIncidents.find(i => i.id === id) ?? null;
  try {
    const res = await fetch(`${API_URL}/incidents/${id}`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    return adaptIncident(await res.json());
  } catch (e) {
    console.error(`[RoadSense] fetchIncidentById(${id}) failed:`, e);
    return null;
  }
}

export async function submitFeedback(data: {
  incidentId:      string;
  resolvedBy:      string;
  resolutionDate:  string;
  resolutionNotes: string;
  actionTaken:     string;
}): Promise<boolean> {
  if (!API_URL) return true;
  try {
    const res = await fetch(`${API_URL}/feedback`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(data),
    });
    return res.ok;
  } catch (e) {
    console.error('[RoadSense] submitFeedback failed:', e);
    return false;
  }
}

// ── Mock fallback ─────────────────────────────────────────────────────────────

export const mockIncidents: Incident[] = [
  {
    id: '1', code: 'INC-2847', confidence: 89,
    origin: 'MG Road', damageType: 'Pothole', damageAbbrev: 'POT',
    severity: 'CRIT', severityColor: '#ef4444',
    signalsDetected: 47, lastUpdated: '2m ago', timestamp: Date.now() - 2 * 60 * 1000,
    languages: [{ flag: '🇮🇳', name: 'Hindi', count: 3 }, { flag: '🇬🇧', name: 'English', count: 1 }],
    sources: [{ name: 'Reddit', count: 3 }, { name: 'News', count: 1 }],
    summary: 'Severe pothole near Shivaji Nagar metro causing traffic disruption',
    explanation: 'Multiple signals detected reporting significant road damage on MG Road near Shivaji Nagar metro station.',
    lat: 12.9756, lng: 77.6083, status: 'active',
  },
  {
    id: '2', code: 'INC-2851', confidence: 92,
    origin: 'Koramangala', damageType: 'Crack', damageAbbrev: 'CRK',
    severity: 'HIGH', severityColor: '#f97316',
    signalsDetected: 34, lastUpdated: '15m ago', timestamp: Date.now() - 15 * 60 * 1000,
    languages: [{ flag: '🇮🇳', name: 'Kannada', count: 2 }, { flag: '🇬🇧', name: 'English', count: 2 }],
    sources: [{ name: 'News', count: 2 }, { name: 'Reddit', count: 1 }],
    summary: 'Road surface cracking on 80ft Road showing progressive deterioration',
    explanation: 'Road surface cracking detected along 80ft Road. Multiple reports confirm progressive deterioration over 48 hours.',
    lat: 12.9352, lng: 77.6245, status: 'active',
  },
];