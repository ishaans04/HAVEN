"use client";

import { useCallback, useEffect, useState } from "react";
import { AuditBar } from "@/components/AuditBar";
import { DecisionPanel } from "@/components/DecisionPanel";
import { ProcedureReasoning } from "@/components/ProcedureReasoning";
import { ReadinessOverview } from "@/components/ReadinessOverview";
import { ScenarioBar } from "@/components/ScenarioBar";
import { ScheduleImpactPanel } from "@/components/ScheduleImpactPanel";
import { TaskRiskTimeline } from "@/components/TaskRiskTimeline";
import { API_BASE, fetchAudit, fetchEvaluation, fetchScenarios } from "@/lib/api";
import type {
  AuditRecord,
  EvaluationResponse,
  ScenarioSummary,
} from "@/lib/types";

const DEFAULT_SCENARIO = "burn_fatigue";

export default function Console() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenarioId, setScenarioId] = useState(DEFAULT_SCENARIO);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [audit, setAudit] = useState<AuditRecord | null>(null);
  const [situationId, setSituationId] = useState<string | null>(null);
  const [crewId, setCrewId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScenarios()
      .then(setScenarios)
      .catch((e: Error) => setError(e.message));
  }, []);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchEvaluation(id);
      setEvaluation(result);
      const first = result.situations[0] ?? null;
      setSituationId(first?.situation_id ?? null);
      // Default the timeline to whoever the Situation concerns; failing that,
      // to the crew member the deterministic tier flagged hardest.
      const fallback =
        [...result.readiness].sort((a, b) => a.alertness_score - b.alertness_score)[0] ?? null;
      setCrewId(first?.crew_member ?? fallback?.crew_member ?? null);
    } catch (e) {
      setError((e as Error).message);
      setEvaluation(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(scenarioId);
  }, [scenarioId, load]);

  const situation =
    evaluation?.situations.find((s) => s.situation_id === situationId) ?? null;

  useEffect(() => {
    if (!situation) {
      setAudit(null);
      return;
    }
    let cancelled = false;
    fetchAudit(situation.audit_ref)
      .then((record) => {
        if (!cancelled) setAudit(record);
      })
      .catch(() => {
        if (!cancelled) setAudit(null);
      });
    return () => {
      cancelled = true;
    };
  }, [situation]);

  const crew =
    evaluation?.readiness.find((c) => c.crew_member === crewId) ??
    evaluation?.readiness[0] ??
    null;

  if (error) {
    return (
      <main className="hv-grid flex min-h-screen items-center justify-center p-8">
        <div className="hv-panel max-w-md p-6">
          <h1 className="text-[14px] font-semibold text-[color:var(--hv-degraded)]">
            Cannot reach the HAVEN engine
          </h1>
          <p className="mono mt-2 text-[11px] text-[var(--hv-muted)]">{error}</p>
          <p className="mt-3 text-[11px] leading-relaxed text-[var(--hv-muted)]">
            The API tier is expected at <span className="mono">{API_BASE}</span>. Start it with{" "}
            <span className="mono">uvicorn app.main:app --reload --port 8000</span> from the{" "}
            <span className="mono">backend/</span> directory.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="hv-grid min-h-screen">
      <ScenarioBar
        scenarios={scenarios}
        selected={scenarioId}
        onSelect={setScenarioId}
        note={evaluation?.scenario_note ?? ""}
        loading={loading}
      />

      {!evaluation ? (
        <div className="p-8 text-[12px] text-[var(--hv-muted)]">Evaluating window…</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 p-3 lg:grid-cols-12">
          <div className="lg:col-span-3">
            <ReadinessOverview
              readiness={evaluation.readiness}
              selectedCrew={crew?.crew_member ?? null}
              onSelect={setCrewId}
            />
          </div>

          <div className="flex flex-col gap-3 lg:col-span-5">
            <TaskRiskTimeline
              crew={crew}
              tasks={evaluation.timeline}
              windowStart={evaluation.window.start}
              selectedSituation={situationId}
              onSelectSituation={(id) => {
                setSituationId(id);
                const target = evaluation.situations.find((s) => s.situation_id === id);
                if (target) setCrewId(target.crew_member);
              }}
            />
            <ProcedureReasoning situation={situation} audit={audit} />
          </div>

          <div className="flex flex-col gap-3 lg:col-span-4">
            <DecisionPanel situation={situation} />
            <ScheduleImpactPanel situation={situation} readiness={evaluation.readiness} />
          </div>

          <div className="lg:col-span-12">
            <AuditBar
              tierStatus={evaluation.tier_status}
              audit={audit}
              evaluationId={evaluation.evaluation_id}
            />
          </div>
        </div>
      )}
    </main>
  );
}
