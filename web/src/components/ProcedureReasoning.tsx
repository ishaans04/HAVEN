"use client";

import clsx from "clsx";
import type {
  AuditRecord,
  ClauseDetail,
  RejectedCandidate,
  RetrievedCandidate,
  Situation,
} from "@/lib/types";
import { ClauseTally, ClauseVerdict } from "./ClauseVerdict";
import { Meter, Panel, Tag } from "./ui";

const TIER_TONE: Record<string, string> = {
  deterministic: "var(--hv-nominal)",
  retrieval: "var(--hv-accent)",
  reasoning: "var(--hv-violet)",
  orchestration: "var(--hv-watch)",
  human: "var(--hv-text)",
};

/**
 * Zone 3 — Procedure Reasoning.
 *
 * Shows the candidate set, which passage was selected, and — the part that
 * matters — why each near-miss was rejected. The operator is meant to verify
 * the recommendation here, not take it on trust.
 */
export function ProcedureReasoning({
  situation,
  audit,
}: {
  situation: Situation | null;
  audit: AuditRecord | null;
}) {
  if (!situation) {
    return (
      <Panel zone="Zone 3" title="Procedure Reasoning">
        <div className="p-6 text-[12px] text-[var(--hv-muted)]">
          No Situation selected. Every task in this window cleared the deterministic trigger.
        </div>
      </Panel>
    );
  }

  const retrieveStep = audit?.steps.find((s) => s.step === "RETRIEVE");
  const selectStep = audit?.steps.find((s) => s.step === "SELECT");
  const verifyStep = audit?.steps.find((s) => s.step === "VERIFY");
  const candidates = (retrieveStep?.outputs.candidates ?? []) as RetrievedCandidate[];
  const rejected = (selectStep?.outputs.rejected ?? []) as RejectedCandidate[];
  // The model's *proposal*. Whether it survived is VERIFY's answer, not this
  // one — a passage the checker rejected must not be shown as the rule that
  // governed.
  const governing = selectStep?.outputs.governing_passage_id as string | null | undefined;
  const verified = verifyStep?.outputs.verified === true;
  const rejectionById = new Map(rejected.map((r) => [r.passage_id, r]));

  // The checker's independent view, evaluated over *every* candidate before the
  // model spoke. Rendering it beside the model's choice is the whole point of
  // propose/dispose: an operator can see that the two agreed, rather than
  // taking the citation on trust.
  const admissibility = audit?.steps.find((s) => s.step === "ADMISSIBILITY");
  const clausesById = (admissibility?.outputs.clauses ?? {}) as Record<string, ClauseDetail[]>;
  const admissibleIds = new Set((admissibility?.outputs.admissible ?? []) as string[]);
  const checkerDisagreed = verifyStep?.outputs.checker_disagreed === true;

  const reasoningSteps = (audit?.steps ?? []).filter((s) =>
    [
      "RETRIEVE",
      "ADMISSIBILITY",
      "SELECT",
      "VERIFY",
      "FUSE",
      "GENERATE",
      "GENERATE_FALLBACK",
      "REFUSE",
      "SCHEDULE_IMPACT",
      "WITHHOLD",
      "DEGRADED",
    ].includes(s.step),
  );

  return (
    <Panel
      zone="Zone 3"
      title="Procedure Reasoning"
      hint="Retrieved candidates, the rule selected, and the reason each near-miss was rejected."
      right={
        governing ? (
          <Tag tone="info">{governing}</Tag>
        ) : (
          <Tag tone="bad">no governing rule</Tag>
        )
      }
    >
      <div className="p-4">
        {checkerDisagreed ? (
          <div className="mb-3 rounded border border-[color:var(--hv-degraded)]/50 bg-[color:var(--hv-degraded)]/[0.07] px-3 py-2">
            <div className="text-[11px] font-semibold text-[color:var(--hv-degraded)]">
              The reasoning tier and the checker disagreed
            </div>
            <p className="mt-1 text-[10px] leading-snug text-[var(--hv-muted)]">
              Resolved by refusing. Disagreement fails closed in both directions: a passage the
              checker rejects is never cited, and a model refusal is never overridden upward.
            </p>
          </div>
        ) : null}

        <div className="hv-zone-label mb-2">Candidate passages (top-k, near-misses included)</div>
        <p className="mb-2 text-[10px] leading-snug text-[var(--hv-dim)]">
          The model reads passage prose only — it never sees the compiled preconditions the checker
          evaluates. Near-misses are retrieved on purpose; rejecting them is the judgement.
        </p>
        <ul className="space-y-2">
          {candidates.map((c) => {
            const isGoverning = c.passage_id === governing;
            const rejection = rejectionById.get(c.passage_id);
            return (
              <li
                key={c.passage_id}
                className={clsx(
                  "rounded border px-3 py-2",
                  isGoverning
                    ? "border-[color:var(--hv-nominal)] bg-[color:var(--hv-nominal)]/[0.06]"
                    : "border-[var(--hv-line)] bg-[var(--hv-panel-raised)]",
                )}
              >
                <div className="flex items-start gap-2">
                  <span className="mono shrink-0 text-[10px] text-[var(--hv-dim)]">
                    {c.passage_id}
                  </span>
                  <span className="min-w-0 flex-1 text-[12px] leading-snug">{c.title}</span>
                  <span className="mono shrink-0 text-[11px] text-[var(--hv-muted)]">
                    {c.relevance.toFixed(3)}
                  </span>
                </div>
                <div className="mt-1.5">
                  <Meter
                    value={c.relevance}
                    height={4}
                    color={isGoverning ? "var(--hv-nominal)" : "var(--hv-line-bright)"}
                  />
                </div>
                <div className="mt-2 grid gap-2 border-t border-[var(--hv-line)] pt-2 sm:grid-cols-2">
                  {/* The model proposes. */}
                  <div>
                    <div className="hv-zone-label mb-1">Model</div>
                    {isGoverning ? (
                      <span className="text-[10px] text-[color:var(--hv-accent)]">
                        proposed as governing
                      </span>
                    ) : rejection ? (
                      <span className="text-[10px] leading-snug text-[var(--hv-muted)]">
                        rejected — {rejection.why}
                      </span>
                    ) : (
                      <span className="text-[10px] text-[var(--hv-dim)]">not selected</span>
                    )}
                  </div>

                  {/* The checker disposes. */}
                  <div>
                    <div className="hv-zone-label mb-1 flex items-center gap-1.5">
                      <span>Checker</span>
                      <ClauseTally clauses={clausesById[c.passage_id] ?? []} />
                      {admissibleIds.has(c.passage_id) ? (
                        <span className="text-[9px] text-[color:var(--hv-nominal)]">admissible</span>
                      ) : (
                        <span className="text-[9px] text-[color:var(--hv-degraded)]">
                          inadmissible
                        </span>
                      )}
                    </div>
                    <ClauseVerdict clauses={clausesById[c.passage_id] ?? []} />
                  </div>
                </div>

                <div className="mt-1.5 flex items-start gap-2">
                  <span className="mono shrink-0 text-[10px] text-[var(--hv-dim)]">
                    {c.doc} §{c.section}
                  </span>
                  {isGoverning ? (
                    verified ? (
                      <Tag tone="good">proposed — verified by the checker</Tag>
                    ) : (
                      <Tag tone="bad">proposed — rejected by the checker</Tag>
                    )
                  ) : rejection ? (
                    <span className="text-[10px] leading-snug text-[color:var(--hv-degraded)]">
                      rejected — {rejection.why}
                    </span>
                  ) : null}
                </div>
              </li>
            );
          })}
          {candidates.length === 0 ? (
            <li className="rounded border border-[var(--hv-line)] px-3 py-2 text-[11px] text-[var(--hv-muted)]">
              Retrieval was not invoked for this Situation.
            </li>
          ) : null}
        </ul>

        <div className="hv-zone-label mb-2 mt-5">Orchestrated reasoning flow</div>
        <ol className="relative space-y-0 border-l border-[var(--hv-line)] pl-4">
          {reasoningSteps.map((step) => (
            <li key={step.seq} className="relative pb-3 last:pb-0">
              <span
                className="absolute -left-[21px] top-1 h-2 w-2 rounded-full"
                style={{ background: TIER_TONE[step.tier] ?? "var(--hv-dim)" }}
              />
              <div className="flex items-baseline gap-2">
                <span className="mono text-[11px] font-semibold">{step.step}</span>
                <span className="mono text-[9px] uppercase tracking-wider text-[var(--hv-dim)]">
                  {step.tier}
                </span>
                <span className="mono ml-auto text-[9px] text-[var(--hv-dim)]">
                  {step.duration_ms.toFixed(1)} ms
                </span>
              </div>
              <p className="mt-0.5 text-[11px] leading-snug text-[var(--hv-muted)]">
                {step.detail}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </Panel>
  );
}
