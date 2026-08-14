import type { AuditRecord, EvaluationResponse, ScenarioSummary } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} on ${path}`);
  }
  return response.json() as Promise<T>;
}

export const fetchScenarios = () => get<ScenarioSummary[]>("/api/scenarios");

export const fetchEvaluation = (scenarioId: string) =>
  get<EvaluationResponse>(`/api/scenarios/${scenarioId}/evaluate`);

export const fetchAudit = (auditRef: string) =>
  get<AuditRecord>(`/api/audit/${auditRef}`);

export async function recordDecision(payload: {
  situation_id: string;
  audit_ref: string;
  decision: "approved" | "overridden";
  reason: string;
}) {
  const response = await fetch(`${API_BASE}/api/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, operator: "flight_surgeon_console" }),
  });
  if (!response.ok) throw new Error(`Failed to record decision: ${response.status}`);
  return response.json();
}
