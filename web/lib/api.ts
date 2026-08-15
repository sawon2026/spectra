/** Typed client for Spectra /api/v1 — never executes local commands. */

const BASE =
  typeof window !== "undefined"
    ? "/backend"
    : process.env.SPECTRA_API_URL || "http://127.0.0.1:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
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
};

export type Workflow = {
  id: string;
  case_id: string;
  status: string;
  investigation_id?: string;
  decision_count: number;
  recovery_notes: string;
};

export type TimelineEntry = {
  id: string;
  kind: string;
  source: string;
  summary: string;
  confidence?: number;
};
