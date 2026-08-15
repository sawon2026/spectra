/** Typed client for Spectra /api/v1 — never executes local commands. */

const BASE =
  typeof window !== "undefined"
    ? "/backend"
    : process.env.SPECTRA_API_URL || "http://127.0.0.1:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text.slice(0, 400)}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  return handle<T>(res);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(res);
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(res);
}

export type Health = {
  status: string;
  version: string;
  policy_gate: string;
  offline_default: boolean;
  ai_configured: boolean;
};

export type Case = {
  id: string;
  name: string;
  description: string;
  status: string;
  tags?: string[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type Scope = {
  auth_status: string;
  network_profile: string;
  ready_for_act: boolean;
  allowed_activities: string[];
  auth_basis?: string;
};

export type Evidence = {
  id: string;
  case_id: string;
  title: string;
  source_type: string;
  content_hash?: string | null;
  confidence?: number;
  source_ref?: string;
};

export type Finding = {
  id: string;
  case_id: string;
  title: string;
  severity: string;
  status: string;
  confidence: number;
};

export type Workflow = {
  id: string;
  case_id: string;
  status: string;
  investigation_id?: string | null;
  decision_count: number;
  recovery_notes: string;
  observation_ids?: string[];
};

export type TimelineEntry = {
  id: string;
  kind: string;
  source: string;
  summary: string;
  confidence?: number | null;
};

export type GraphNode = {
  id: string;
  case_id?: string | null;
  node_type: string;
  label: string;
};

export type GraphEdge = {
  id: string;
  relation: string;
  from_node_id: string;
  to_node_id: string;
};

export type Capability = {
  name: string;
  category: string;
  risk_level: string;
  requires_authorization: boolean;
  description: string;
};

export type Plugin = {
  name: string;
  version: string;
  state: string;
  health: string;
};

export function reportUrl(caseId: string, format: "markdown" | "json" | "html" | "pdf"): string {
  return `${BASE}/api/v1/reports/${caseId}/${format}`;
}
