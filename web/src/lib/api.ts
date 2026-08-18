import type {
  AuditRecord,
  EvaluationResponse,
  ProcedureSummary,
  ScenarioSummary,
} from "./types";

/**
 * Where the API lives.
 *
 * Empty by default, meaning same-origin: in the shipped container FastAPI
 * serves both the console and the API, so a relative path is correct and a
 * hardcoded host would break the moment it was deployed anywhere.
 *
 * `npm run dev` sets it to localhost:8000, because in development the console
 * and the API genuinely are two processes on two ports.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

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

/** The corpus itself. Implemented since v1; nothing called it until now. */
export const fetchProcedures = () => get<ProcedureSummary[]>("/api/procedures");

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
