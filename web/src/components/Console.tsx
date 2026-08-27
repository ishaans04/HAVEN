"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Answer } from "@/components/Answer";
import { ArgumentWalk, BEATS } from "@/components/ArgumentWalk";
import { AskScreen } from "@/components/AskScreen";
import { AuditBar, TierStrip } from "@/components/AuditBar";
import { CrewDetail, CrewRail } from "@/components/CrewRail";
import { OrbitDial, OrbitLegend } from "@/components/OrbitDial";
import { ProcedureBrowser } from "@/components/ProcedureBrowser";
import { ProcedureReasoning } from "@/components/ProcedureReasoning";
import { Scene } from "@/components/Scene";
import { TaskRiskTimeline } from "@/components/TaskRiskTimeline";
import { TopBar } from "@/components/TopBar";
import { Tour, tourSeen } from "@/components/Tour";
import { ChevronDown } from "lucide-react";
import { Disclosure, GlassCard, Label } from "@/components/ui";
import { VerdictCard } from "@/components/VerdictCard";
import { answerFor } from "@/lib/ask";
import { API_BASE, fetchAudit, fetchEvaluation, fetchScenarios } from "@/lib/api";
import type { AuditRecord, EvaluationResponse, ScenarioSummary } from "@/lib/types";

const DEFAULT_SCENARIO = "burn_fatigue";

/**
 * The console, as a consultation.
 *
 * It used to be a monitoring dashboard: six zones live at once, 217 elements and
 * 181 words in the first view, a 184px masthead, four ways to navigate. That is
 * the right shape for somebody who watches a screen for eight hours and needs
 * everything in peripheral vision. It is the wrong shape for somebody meeting
 * the system for the first time, because it makes them do the work of deciding
 * what matters.
 *
 * So the page asks one question and answers it.
 *
 * **The question and the answer** lead, at the size of the claim. Everything a
 * person needs in order to believe the answer follows underneath in the order
 * they would ask for it: why, then how it decided, then the proof.
 *
 * **The scene** — Earth, the stars, the day as a dial — is the setting rather
 * than a panel. The dial is unboxed and sticky beside the answer, so the state
 * of the crew is ambient context you glance at, not a card you have to read.
 *
 * Nothing was removed. Every figure, clause, candidate, timing and hash from v1
 * is still reachable; it is sequenced behind the answer instead of competing
 * with it.
 */
export function Console() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenarioId, setScenarioId] = useState(DEFAULT_SCENARIO);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [audit, setAudit] = useState<AuditRecord | null>(null);
  const [situationId, setSituationId] = useState<string | null>(null);
  const [crewId, setCrewId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showProcedures, setShowProcedures] = useState(false);
  const [asking, setAsking] = useState(false);
  const [tour, setTour] = useState(false);
  // null when not walking. The walk drives the scenario, not the reverse.
  const [beat, setBeat] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tourOffered = useRef(false);

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

  // Publish the bar's height so the sticky dial can clear it.
  useEffect(() => {
    const bar = document.querySelector("header");
    if (!bar) return;
    const publish = () =>
      document.documentElement.style.setProperty(
        "--masthead-h",
        `${Math.round(bar.getBoundingClientRect().height)}px`,
      );
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(bar);
    return () => observer.disconnect();
  }, []);

  // Offer the tour once the console has something in it. Offering it against an
  // empty page would spotlight cards that are not there yet.
  useEffect(() => {
    if (!evaluation || tourOffered.current) return;
    tourOffered.current = true;
    if (!tourSeen()) setTour(true);
  }, [evaluation]);

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

  const selectSituation = (id: string) => {
    setSituationId(id);
    const target = evaluation?.situations.find((s) => s.situation_id === id);
    if (target) setCrewId(target.crew_member);
  };

  // The room takes its colour from the answer. A refusal cools it without a
  // single word changing.
  const tone = answerFor(situation).tone;

  if (error) {
    return (
      <>
        <Scene tone="bad" />
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
            <p className="mt-3 text-[13px] leading-relaxed text-[var(--ink-3)]">
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
      <Scene tone={tone} />

      <TopBar
        onAsk={() => setAsking(true)}
        onOpenProcedures={() => setShowProcedures(true)}
        onStartTour={() => setTour(true)}
        walking={beat !== null}
        onStartWalk={() => {
          setBeat(0);
          setScenarioId(BEATS[0].scenario);
        }}
      />

      {asking ? (
        <AskScreen
          scenarios={scenarios}
          selected={scenarioId}
          onSelect={(id) => {
            // Choosing a case by hand means leaving the guided sequence.
            setBeat(null);
            setScenarioId(id);
          }}
          onClose={() => setAsking(false)}
        />
      ) : null}

      {showProcedures ? <ProcedureBrowser onClose={() => setShowProcedures(false)} /> : null}
      <Tour open={tour} onClose={() => setTour(false)} />

      <main className="mx-auto max-w-[1400px] px-5 pb-24 pt-6 sm:px-8">
        {beat !== null ? (
          <ArgumentWalk
            index={beat}
            onIndex={(next) => {
              setBeat(next);
              setScenarioId(BEATS[next].scenario);
            }}
            onClose={() => setBeat(null)}
          />
        ) : null}

        {!evaluation ? (
          <Skeleton />
        ) : (
          <div className="grid gap-x-10 gap-y-8 lg:grid-cols-12">
            {/* ---------------------------------------------------------------
                The consultation. One question, one answer, then the case for
                it in the order a person would ask for it.
                --------------------------------------------------------------- */}
            <div className="min-w-0 lg:col-span-7">
              {/* The answer owns the first screen. Everything under it is the
                  case for it, and the reader should meet the two in that
                  order rather than at the same time. */}
              <div
                className="rise flex flex-col lg:min-h-[calc(100svh-var(--masthead-h,56px)-104px)]"
                data-tour="verdict"
              >
                <Answer situation={situation} />

                {/* The roster, in the space the answer was not using.

                    It sat under the dial in the right column, which made that
                    column taller than the viewport -- and a `sticky` element
                    taller than the viewport cannot be scrolled to the bottom
                    of, so the last two operators were unreachable. Moving it
                    here fixes that by subtraction, fills a screen's worth of
                    empty left margin, and puts the one genuinely interactive
                    control on this page where a reader is already looking. */}
                <div className="mt-auto pt-10" data-tour="crew">
                  <div className="mb-1 flex flex-wrap items-baseline gap-x-3">
                    <Label>Crew readiness</Label>
                    <span className="mono text-[11px] text-[var(--ink-3)]">
                      {evaluation.readiness.length} operators
                    </span>
                  </div>
                  {/* Says what the click does, and who the answer is about --
                      the two things that were previously left to be inferred
                      from a dial quietly changing shape. */}
                  <p className="mb-3 text-[12px] leading-snug text-[var(--ink-3)]">
                    Pick anyone to put their day on the dial.
                    {situation ? (
                      <>
                        {" "}
                        The answer above is about{" "}
                        <span className="text-[var(--ink-2)]">
                          {situation.crew_member_name}
                        </span>
                        , the only operator HAVEN raised in this window.
                      </>
                    ) : null}
                  </p>
                  <CrewRail
                    readiness={evaluation.readiness}
                    selected={crew?.crew_member ?? null}
                    onSelect={setCrewId}
                  />
                </div>

                <a
                  href="#why"
                  className="group mt-6 hidden items-center gap-2 text-[12px] uppercase tracking-[0.14em] text-[var(--ink-3)] transition-colors hover:text-[var(--accent)] lg:flex"
                >
                  <ChevronDown
                    size={14}
                    className="transition-transform duration-500 group-hover:translate-y-1"
                  />
                  {situation ? "Why HAVEN says so" : "What the system checked"}
                </a>
              </div>

              {situation ? (
                <div className="space-y-4 lg:pt-4" id="why">
                  <div className="rise" style={{ animationDelay: "120ms" }}>
                    <VerdictCard situation={situation} readiness={evaluation.readiness} />
                  </div>
                  <div className="rise" style={{ animationDelay: "180ms" }}>
                    <ProcedureReasoning situation={situation} audit={audit} />
                  </div>
                </div>
              ) : null}

              <div className="rise mt-4" style={{ animationDelay: "240ms" }} data-tour="audit">
                <AuditBar tierStatus={evaluation.tier_status} audit={audit} />
              </div>

              {/* The readings behind the dial. Detail about the evidence,
                  so it belongs with the evidence rather than in the scene. */}
              <div className="rise mt-4" style={{ animationDelay: "280ms" }}>
                <Disclosure
                  summary="The readings, as a chart"
                  hint="Every task in the window, and the curve with values you can read off"
                >
                  <TaskRiskTimeline
                    crew={crew}
                    tasks={evaluation.timeline}
                    windowStart={evaluation.window.start}
                    selectedSituation={situationId}
                    onSelectSituation={selectSituation}
                  />
                </Disclosure>

                <Disclosure
                  summary="Every operator, every figure"
                  hint="Baseline, workload, sleep debt, hours awake, window low and record coverage"
                >
                  <div className="glass-2 px-1 py-2">
                    <CrewDetail readiness={evaluation.readiness} />
                  </div>
                </Disclosure>
              </div>

              {/* What this case is here to show. Backend copy, kept as a
                  footnote: it is commentary about the demonstration rather
                  than part of the answer. */}
              {evaluation.scenario_note ? (
                <p className="mt-6 max-w-2xl text-[12px] leading-relaxed text-[var(--ink-3)]">
                  <span className="uppercase tracking-[0.14em]">About this case</span>
                  {" · "}
                  {evaluation.scenario_note}
                </p>
              ) : null}

              {/* How the answer was produced, under the note about why this
                  case exists. Both are commentary on the run rather than part
                  of the answer, so they read as one footnote. Grouped by a
                  hairline rather than a box, like every other aside here. */}
              <div className="divide-top mt-5 pt-4">
                <TierStrip
                  tierStatus={evaluation.tier_status}
                  evaluationId={evaluation.evaluation_id}
                />
              </div>
            </div>

            {/* ---------------------------------------------------------------
                The scene. The day as a dial, unboxed and sticky: ambient
                context you glance at rather than a card you have to read.
                --------------------------------------------------------------- */}
            <div className="min-w-0 lg:col-span-5 lg:col-start-8 lg:row-start-1">
              {/* Sticky, and bounded. A sticky element taller than the space
                  it sticks in has an unreachable bottom -- the reason the
                  roster below the dial could not be scrolled to. The roster
                  has moved out, and the cap plus `overflow-y-auto` means that
                  if this ever outgrows the viewport again it scrolls instead
                  of silently truncating. `no-bar` keeps the scrollbar from
                  appearing across the scene when it is not needed. */}
              <div
                className="no-bar lg:sticky lg:max-h-[calc(100svh-var(--masthead-h,56px)-32px)] lg:overflow-y-auto"
                style={{ top: "calc(var(--masthead-h, 56px) + 16px)" }}
              >
                <div data-tour="dial">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                    {/* Whose day this is. The dial swapped silently when a
                        different operator was picked, which reads as nothing
                        having happened. */}
                    <Label>{crew ? `${crew.name} · 24 h` : "The window"}</Label>
                    <span className="mono text-[11px] text-[var(--ink-3)]">
                      {evaluation.window.start.slice(0, 10)}
                    </span>
                  </div>

                  {/* The two figures that shape the curve above.

                      The roster is synthetic and several operators share
                      inputs -- three distinct curves across six people -- so
                      switching between two of them changes the name and
                      nothing else on the dial. Printing what drives the shape
                      makes that legible rather than mysterious: two operators
                      look alike because they have been awake the same time
                      and carry the same debt. */}
                  {crew ? (
                    <p className="readout mt-1 text-[11px] text-[var(--ink-3)]">
                      {crew.hours_awake.toFixed(1)} h awake · {crew.sleep_debt_h.toFixed(1)} h sleep
                      debt · baseline {crew.baseline_alertness.toFixed(2)}
                    </p>
                  ) : null}

                  <div className="mx-auto w-full max-w-[560px]">
                    <OrbitDial
                      crew={crew}
                      tasks={evaluation.timeline}
                      windowStart={evaluation.window.start}
                      selectedSituation={situationId}
                      onSelectSituation={selectSituation}
                      loading={loading}
                    />
                  </div>

                  <OrbitLegend className="mt-1" />
                </div>

              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
}

/** First paint, before the engine has answered. Glass, not a spinner. */
function Skeleton() {
  return (
    <div className="grid gap-10 lg:grid-cols-12" aria-busy="true" aria-live="polite">
      <div className="flex flex-col gap-4 lg:col-span-7">
        <GlassCard className="h-40" loading />
        <GlassCard className="h-72" loading />
      </div>
      <GlassCard className="lg:col-span-5" loading>
        <div className="aspect-square" />
      </GlassCard>
      <span className="sr-only">Evaluating the window</span>
    </div>
  );
}
