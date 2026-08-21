"use client";

import { useCallback, useEffect, useState } from "react";
import { AuditBar } from "@/components/AuditBar";
import { CrewDetail, CrewRail } from "@/components/CrewRail";
import { OrbitDial, OrbitLegend } from "@/components/OrbitDial";
import { ProcedureBrowser } from "@/components/ProcedureBrowser";
import { ProcedureReasoning } from "@/components/ProcedureReasoning";
import { ScenarioBar } from "@/components/ScenarioBar";
import { StarField } from "@/components/StarField";
import { TaskRiskTimeline } from "@/components/TaskRiskTimeline";
import { Disclosure, GlassCard, Label } from "@/components/ui";
import { VerdictCard } from "@/components/VerdictCard";
import { API_BASE, fetchAudit, fetchEvaluation, fetchScenarios } from "@/lib/api";
import type { AuditRecord, EvaluationResponse, ScenarioSummary } from "@/lib/types";

const DEFAULT_SCENARIO = "burn_fatigue";

/**
 * The console.
 *
 * Three layers, deliberately ordered by who is reading.
 *
 * **The answer** — the dial and the verdict card, side by side above the fold.
 * Somebody who has never seen this should be able to read what is being
 * recommended, to whom, and why, without opening anything.
 *
 * **How it decided** — four counts and the cited rule, below.
 *
 * **The instrument** — every figure, clause, candidate, timing and hash from v1,
 * intact, behind disclosures. Nothing was removed to simplify the first read.
 */
export default function Console() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenarioId, setScenarioId] = useState(DEFAULT_SCENARIO);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [audit, setAudit] = useState<AuditRecord | null>(null);
  const [situationId, setSituationId] = useState<string | null>(null);
  const [crewId, setCrewId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showProcedures, setShowProcedures] = useState(false);
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
      // Default the dial to whoever the Situation concerns; failing that, to
      // the crew member the deterministic tier flagged hardest.
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
      <>
        <StarField />
        <main className="flex min-h-screen items-center justify-center p-6">
          <GlassCard className="max-w-lg p-7">
            <h1 className="display text-[26px] text-[var(--bad)]">Cannot reach the HAVEN engine</h1>
            <p className="mono mt-3 text-[12px] text-[var(--ink-2)]">{error}</p>
            <p className="mt-4 text-[13px] leading-relaxed text-[var(--ink-2)]">
              The API tier is expected at{" "}
              <span className="mono">{API_BASE || "this origin"}</span>. Start it from the
              repository root with:
            </p>
            <pre className="glass-2 mono mt-3 overflow-x-auto px-4 py-3 text-[12px] text-[var(--ink)]">
              uv run --no-sync python -m scripts.run_haven
            </pre>
            <p className="mt-3 text-[12.5px] leading-relaxed text-[var(--ink-3)]">
              The launcher reports whether the console is built, which provider chain will be tried,
              and which corpus manifest is loaded, then serves both tiers on one port.
            </p>
          </GlassCard>
        </main>
      </>
    );
  }

  return (
    <>
      <StarField />
      <ScenarioBar
        scenarios={scenarios}
        selected={scenarioId}
        onSelect={setScenarioId}
        note={evaluation?.scenario_note ?? ""}
        loading={loading}
        onOpenProcedures={() => setShowProcedures(true)}
      />

      {showProcedures ? <ProcedureBrowser onClose={() => setShowProcedures(false)} /> : null}

      <main className="mx-auto max-w-[1560px] px-5 pb-14 pt-5 sm:px-8">
        {!evaluation ? (
          <Skeleton />
        ) : (
          <>
            {/* Zone 1 — who is running low. */}
            <section className="rise">
              <div className="mb-2.5 flex flex-wrap items-baseline gap-x-3">
                <Label>Crew readiness</Label>
                <span className="text-[12px] text-[var(--ink-3)]">
                  Predicted alertness against each operator&rsquo;s own baseline — select one to put
                  them on the dial
                </span>
              </div>
              <CrewRail
                readiness={evaluation.readiness}
                selected={crew?.crew_member ?? null}
                onSelect={setCrewId}
              />
            </section>

            <div className="mt-4 grid gap-4 lg:grid-cols-12">
              {/* Zone 2 — the day, as a dial. */}
              <GlassCard
                className="flex flex-col p-5 lg:col-span-5"
                loading={loading}
                style={{ animationDelay: "60ms" }}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <Label>The window</Label>
                  <span className="mono text-[11px] text-[var(--ink-3)]">
                    24 h · midnight at the top
                  </span>
                </div>

                <div className="mx-auto w-full max-w-[520px]">
                  <OrbitDial
                    crew={crew}
                    tasks={evaluation.timeline}
                    windowStart={evaluation.window.start}
                    selectedSituation={situationId}
                    onSelectSituation={(id) => {
                      setSituationId(id);
                      const target = evaluation.situations.find((s) => s.situation_id === id);
                      if (target) setCrewId(target.crew_member);
                    }}
                    loading={loading}
                  />
                </div>

                <OrbitLegend className="mt-1" />

                <div className="mt-4 space-y-2">
                  <Disclosure
                    summary="The readings, as a chart"
                    hint="Every task in the window, and the curve with values you can read off"
                  >
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
                  </Disclosure>

                  <Disclosure
                    summary="The numbers, for every operator"
                    hint="Baseline, workload, sleep debt, hours awake, window low and record coverage"
                  >
                    <div className="glass-2 px-1 py-2">
                      <CrewDetail readiness={evaluation.readiness} />
                    </div>
                  </Disclosure>
                </div>
              </GlassCard>

              {/* Zones 4, 5 and 3 — the answer, then how it was reached. */}
              <div className="flex flex-col gap-4 lg:col-span-7">
                <div className="rise" style={{ animationDelay: "120ms" }}>
                  <VerdictCard situation={situation} readiness={evaluation.readiness} />
                </div>
                <div className="rise" style={{ animationDelay: "180ms" }}>
                  <ProcedureReasoning situation={situation} audit={audit} />
                </div>
              </div>
            </div>

            {/* Zone 6 — the audit strip. */}
            <div className="rise mt-4" style={{ animationDelay: "240ms" }}>
              <AuditBar
                tierStatus={evaluation.tier_status}
                audit={audit}
                evaluationId={evaluation.evaluation_id}
              />
            </div>
          </>
        )}
      </main>
    </>
  );
}

/** First paint, before the engine has answered. Glass, not a spinner. */
function Skeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-12" aria-busy="true" aria-live="polite">
      <GlassCard className="lg:col-span-5" loading>
        <div className="aspect-square" />
      </GlassCard>
      <div className="flex flex-col gap-4 lg:col-span-7">
        <GlassCard className="h-72" loading />
        <GlassCard className="h-52" loading />
      </div>
      <span className="sr-only">Evaluating the window</span>
    </div>
  );
}
