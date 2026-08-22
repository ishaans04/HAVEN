"use client";

import clsx from "clsx";
import { Calculator, FileSearch, Gavel, MessageSquareQuote } from "lucide-react";
import type {
  AuditRecord,
  ClauseDetail,
  RejectedCandidate,
  RetrievedCandidate,
  Situation,
} from "@/lib/types";
import { ClauseTally, ClauseVerdict } from "./ClauseVerdict";
import { Chip, Disclosure, GlassCard, Label, Meter, TONE_VAR } from "./ui";

const TIER_TONE: Record<string, string> = {
  deterministic: "var(--ok)",
  retrieval: "var(--info)",
  reasoning: "var(--iris)",
  orchestration: "var(--warn)",
  human: "var(--ink)",
};

const FLOW_STEPS = [
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
];

/**
 * Zone 3 — how the answer was reached.
 *
 * v1 opened with the candidate set: four passages, each with a similarity
 * score, a prose verdict, and a per-clause precondition table. That is the most
 * defensible screen in the system and the least legible one, and it was the
 * first thing a newcomer met.
 *
 * The same content is here, in two layers. The top layer is four counts —
 * measured, offered, allowed, cited — which is the whole architecture stated in
 * numbers a layman can hold: the maths went first, retrieval offered more than
 * one option, a deterministic checker threw most of them out, and the citation
 * that survived is the one on the card above.
 *
 * The clause tables sit under it, unchanged. Somebody auditing this needs every
 * line of them; somebody meeting it needs to know they exist.
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
      <GlassCard className="p-6">
        <Label>How it decided</Label>
        <p className="mt-2.5 text-[13px] leading-relaxed text-[var(--ink-2)]">
          No Situation was raised, so no procedure was consulted. Every task in this window cleared
          the deterministic trigger on the numbers alone.
        </p>
      </GlassCard>
    );
  }

  const step = (name: string) => audit?.steps.find((s) => s.step === name);
  const retrieveStep = step("RETRIEVE");
  const selectStep = step("SELECT");
  const verifyStep = step("VERIFY");
  const admissibility = step("ADMISSIBILITY");

  const candidates = (retrieveStep?.outputs.candidates ?? []) as RetrievedCandidate[];
  const rejected = (selectStep?.outputs.rejected ?? []) as RejectedCandidate[];
  const governing = selectStep?.outputs.governing_passage_id as string | null | undefined;
  const verified = verifyStep?.outputs.verified === true;
  const checkerDisagreed = verifyStep?.outputs.checker_disagreed === true;
  const clausesById = (admissibility?.outputs.clauses ?? {}) as Record<string, ClauseDetail[]>;
  const admissibleIds = new Set((admissibility?.outputs.admissible ?? []) as string[]);
  const rejectionById = new Map(rejected.map((r) => [r.passage_id, r]));
  const flow = (audit?.steps ?? []).filter((s) => FLOW_STEPS.includes(s.step));
  const citation = situation.recommendation?.citation;

  return (
    <GlassCard className="overflow-hidden">
      <div className="flex flex-wrap items-start gap-3 px-6 pt-5">
        <div className="min-w-0 flex-1">
          <Label>How it decided</Label>
          {/* This said the maths-owns-the-numbers line, which the masthead is
              already saying six inches above it. A slogan restated on the same
              screen stops being a principle and becomes filler. The four counts
              below demonstrate it; they do not need it announced. */}
          <p className="mono mt-1.5 text-[11px] text-[var(--ink-3)]">
            {situation.situation_id}
          </p>
        </div>
        {governing ? (
          <Chip tone={verified ? "ok" : "bad"}>
            {governing} {verified ? "verified" : "rejected by checker"}
          </Chip>
        ) : (
          <Chip tone="bad">no governing rule</Chip>
        )}
      </div>

      {checkerDisagreed ? (
        <div
          className="mx-6 mt-4 rounded-[var(--radius-sm)] px-4 py-3"
          style={{
            background: "rgba(255,128,149,0.08)",
            boxShadow: "inset 0 0 0 1px rgba(255,128,149,0.28)",
          }}
        >
          <div className="text-[13px] font-medium text-[var(--bad)]">
            The reasoning tier and the checker disagreed
          </div>
          <p className="mt-1 text-[12.5px] leading-snug text-[var(--ink-2)]">
            Resolved by refusing. Disagreement fails closed in both directions: a passage the
            checker rejects is never cited, and a model refusal is never overridden upward.
          </p>
        </div>
      ) : null}

      {/* The four counts. */}
      <div className="mt-5 grid gap-2.5 px-6 sm:grid-cols-2 xl:grid-cols-4">
        <Count
          icon={<Calculator size={14} />}
          tone="ok"
          n={situation.alertness_score.toFixed(2)}
          label="Measured"
          body="Alertness and workload, computed deterministically before any model was asked anything."
        />
        <Count
          icon={<FileSearch size={14} />}
          tone="info"
          n={String(candidates.length)}
          label="Offered"
          body="Passages retrieved for this situation, near-misses deliberately included."
        />
        <Count
          icon={<Gavel size={14} />}
          tone={admissibleIds.size ? "warn" : "bad"}
          n={`${admissibleIds.size}/${candidates.length || 0}`}
          label="Allowed"
          body="Survived the compiled preconditions, checked independently of the model."
        />
        <Count
          icon={<MessageSquareQuote size={14} />}
          tone={citation ? "iris" : "bad"}
          n={citation ? `§${citation.section}` : "none"}
          label="Cited"
          body={
            citation
              ? `${citation.doc} — proposed by the model and confirmed clause by clause.`
              : "Nothing cleared the checker, so nothing was cited and the flow refused."
          }
        />
      </div>

      {/* The specialist layers. */}
      <div className="mt-4 space-y-2 px-6 pb-6">
        <Disclosure
          summary="Every candidate, and the checker's verdict on each"
          hint="The model reads passage prose only — it never sees the compiled preconditions the checker evaluates."
        >
          <ul className="space-y-2.5">
            {candidates.map((candidate) => {
              const isGoverning = candidate.passage_id === governing;
              const rejection = rejectionById.get(candidate.passage_id);
              const admissible = admissibleIds.has(candidate.passage_id);
              return (
                <li
                  key={candidate.passage_id}
                  className="glass-2 px-4 py-3"
                  style={
                    isGoverning
                      ? {
                          background: "rgba(92,228,191,0.07)",
                          boxShadow: "inset 0 0 0 1px rgba(92,228,191,0.3)",
                        }
                      : undefined
                  }
                >
                  <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                    <span className="mono text-[11.5px] text-[var(--ink-3)]">
                      {candidate.passage_id}
                    </span>
                    <span className="min-w-0 flex-1 text-[13px] leading-snug text-[var(--ink)]">
                      {candidate.title}
                    </span>
                    <span className="mono text-[11.5px] text-[var(--ink-3)]">
                      {candidate.doc} §{candidate.section}
                    </span>
                  </div>

                  <div className="mt-2.5">
                    <Meter
                      value={candidate.relevance}
                      height={3}
                      color={isGoverning ? "var(--ok)" : "rgba(255,255,255,0.32)"}
                    />
                  </div>

                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label>The model proposed</Label>
                      <p className="mt-1 text-[12px] leading-snug text-[var(--ink-2)]">
                        {isGoverning
                          ? "This passage, as governing."
                          : rejection
                            ? `Rejected — ${rejection.why}`
                            : "Not selected."}
                      </p>
                    </div>
                    <div>
                      <Label className="flex items-center gap-2">
                        <span>The checker found</span>
                        <ClauseTally clauses={clausesById[candidate.passage_id] ?? []} />
                        <span
                          className="text-[10px] tracking-normal"
                          style={{ color: admissible ? "var(--ok)" : "var(--bad)" }}
                        >
                          {admissible ? "admissible" : "inadmissible"}
                        </span>
                      </Label>
                      <div className="mt-1.5">
                        <ClauseVerdict clauses={clausesById[candidate.passage_id] ?? []} />
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
            {candidates.length === 0 ? (
              <li className="glass-2 px-4 py-3 text-[12.5px] text-[var(--ink-2)]">
                Retrieval was not invoked for this Situation.
              </li>
            ) : null}
          </ul>
        </Disclosure>

        <Disclosure
          summary="The orchestrated flow, step by step"
          hint={`${flow.length} steps, each logged with the tier that ran it and what it took`}
        >
          <ol className="space-y-0 pl-1">
            {flow.map((s) => (
              <li key={s.seq} className="relative flex gap-3.5 pb-3.5 last:pb-0">
                <span className="relative flex w-3 shrink-0 justify-center">
                  <span
                    className="absolute top-[6px] h-2 w-2 rounded-full"
                    style={{
                      background: TIER_TONE[s.tier] ?? "var(--ink-3)",
                      boxShadow: `0 0 8px ${TIER_TONE[s.tier] ?? "transparent"}`,
                    }}
                  />
                  <span className="absolute top-[18px] bottom-[-6px] w-px bg-white/10" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-baseline gap-x-2.5">
                    <span className="mono text-[12px] font-medium text-[var(--ink)]">{s.step}</span>
                    <span
                      className="text-[10.5px] uppercase tracking-[0.14em]"
                      style={{ color: TIER_TONE[s.tier] ?? "var(--ink-3)" }}
                    >
                      {s.tier}
                    </span>
                    <span className="mono ml-auto text-[11px] text-[var(--ink-3)]">
                      {s.duration_ms.toFixed(1)} ms
                    </span>
                  </span>
                  <span className="mt-0.5 block text-[12.5px] leading-snug text-[var(--ink-2)]">
                    {s.detail}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </Disclosure>
      </div>
    </GlassCard>
  );
}

function Count({
  icon,
  n,
  label,
  body,
  tone,
}: {
  icon: React.ReactNode;
  n: string;
  label: string;
  body: string;
  tone: "ok" | "info" | "warn" | "bad" | "iris";
}) {
  const color = TONE_VAR[tone];
  return (
    <div className="glass-2 px-4 py-3.5">
      <div className="flex items-center gap-2" style={{ color }}>
        {icon}
        <span className={clsx("text-[10.5px] uppercase tracking-[0.15em]")}>{label}</span>
      </div>
      <div className="readout mt-2 text-[24px] leading-none text-[var(--ink)]">{n}</div>
      <p className="mt-2 text-[11.5px] leading-snug text-[var(--ink-3)]">{body}</p>
    </div>
  );
}
