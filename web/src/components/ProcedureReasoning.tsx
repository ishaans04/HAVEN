"use client";

import clsx from "clsx";
import type {
  AuditRecord,
  RejectedCandidate,
  RetrievedCandidate,
  Situation,
} from "@/lib/types";
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
  const candidates = (retrieveStep?.outputs.candidates ?? []) as RetrievedCandidate[];
  const rejected = (selectStep?.outputs.rejected ?? []) as RejectedCandidate[];
  const governing = selectStep?.outputs.governing_passage_id as string | null | undefined;
  const rejectionById = new Map(rejected.map((r) => [r.passage_id, r]));

  const reasoningSteps = (audit?.steps ?? []).filter((s) =>
    ["RETRIEVE", "SELECT", "GATE", "FUSE", "GENERATE", "GENERATE_FALLBACK", "REFUSE", "SCHEDULE_IMPACT", "WITHHOLD", "DEGRADED"].includes(
      s.step,
    ),
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
        <div className="hv-zone-label mb-2">Candidate passages (top-k, near-misses included)</div>
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
                <div className="mt-1.5 flex items-start gap-2">
                  <span className="mono shrink-0 text-[10px] text-[var(--hv-dim)]">
                    {c.doc} §{c.section}
                  </span>
                  {isGoverning ? (
                    <Tag tone="good">selected — preconditions satisfied</Tag>
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
