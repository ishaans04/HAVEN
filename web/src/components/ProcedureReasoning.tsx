"use client";

import type {
  AuditRecord,
  ClauseDetail,
  RejectedCandidate,
  RetrievedCandidate,
  Situation,
} from "@/lib/types";
import { ClauseTally, ClauseVerdict } from "./ClauseVerdict";
import { Term } from "./Term";
import { Counterfactual, verdictFromAudit } from "./Counterfactual";
import { FlowTrack } from "./FlowTrack";
import { RetrievalFunnel } from "./RetrievalFunnel";
import { Disclosure, GlassCard, Label, Meter } from "./ui";


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
        <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-2)]">
          Nothing was flagged, so no procedure needed looking up. Every task in this window came
          through on the numbers alone.
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

  // One lane per retrieved passage, carrying the clause tally that decided it.
  const lanes = candidates.map((candidate) => {
    const clauses = clausesById[candidate.passage_id] ?? [];
    return {
      passageId: candidate.passage_id,
      relevance: candidate.relevance,
      admissible: admissibleIds.has(candidate.passage_id),
      met: clauses.filter((c) => c.satisfied).length,
      total: clauses.length,
      // Per clause, not just counted: the funnel shows *which* condition
      // killed a lane, which is the question "3/4" raises and cannot answer.
      flags: clauses.map((c) => c.satisfied),
      why: rejectionById.get(candidate.passage_id)?.why ?? null,
    };
  });
  const citation = situation.recommendation?.citation;

  // What ranking on the retrieval score alone would have selected, and what the
  // checker did with it. The most persuasive thing this card can say — and the
  // landing page now says it too, so the derivation lives in one place.
  const verdict = verdictFromAudit(situation, audit);

  return (
    <GlassCard className="overflow-hidden">
      <div className="flex flex-wrap items-start gap-3 px-5 pt-5">
        <div className="min-w-0 flex-1">
          <Label>How it decided</Label>
          {/* This said the maths-owns-the-numbers line, which the masthead is
              already saying six inches above it. A slogan restated on the same
              screen stops being a principle and becomes filler. The four counts
              below demonstrate it; they do not need it announced. */}
          <p className="mono mt-2 text-[11px] text-[var(--ink-3)]">
            {situation.situation_id}
          </p>
        </div>
        {/* The passage and the checker's verdict on it, as two readings rather
            than one capsule. They are different kinds of fact — an identifier
            and a state — and running them together in a pill made the identifier
            look like part of the status. Splitting them lets the verdict sit at
            label weight in its own colour, which matters most in the case this
            whole product exists to show: a passage the retrieval tier scored at
            the top and the checker threw out anyway. */}
        {governing ? (
          <div className="shrink-0 text-right">
            <div className="mono text-[12px] text-[var(--ink-2)]">{governing}</div>
            <div className="label mt-1" style={{ color: verified ? "var(--ok)" : "var(--bad)" }}>
              {verified ? "verified" : "rejected by checker"}
            </div>
          </div>
        ) : (
          <div className="label shrink-0 text-right" style={{ color: "var(--bad)" }}>
            no rule applies
          </div>
        )}
      </div>

      {checkerDisagreed ? (
        <div
          className="mx-5 mt-4 rounded-[var(--radius-sm)] px-4 py-3"
          style={{
            background: "color-mix(in oklab, var(--bad) 8%, transparent)",
            boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--bad) 28%, transparent)",
          }}
        >
          <div className="text-[13px] font-medium text-[var(--bad)]">
            The reasoning tier and the checker disagreed
          </div>
          <p className="mt-1 text-[13px] leading-snug text-[var(--ink-2)]">
            Resolved by refusing. Disagreement fails closed in both directions: a passage the
            checker rejects is never cited, and a model refusal is never overridden upward.
          </p>
        </div>
      ) : null}

      {/* Four rules in, one citation out. The tiles that used to sit here spent
          forty-six words describing this; the diagram performs it. */}
      <div className="mt-5 px-5">
        <RetrievalFunnel lanes={lanes} citation={citation} />
      </div>

      {verdict ? (
        <div className="mt-4 px-5">
          <Counterfactual verdict={verdict} />
        </div>
      ) : null}

      {/* The specialist layers. */}
      <div className="mt-4 space-y-2 px-5 pb-5">
        <Disclosure
          summary="Every rule considered, and what the checker said"
          hint="The AI reads only the wording of each rule. It never sees the conditions the checker will test it against."
        >
          <ul className="space-y-3">
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
                          background: "color-mix(in oklab, var(--ok) 7%, transparent)",
                          boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--ok) 30%, transparent)",
                        }
                      : undefined
                  }
                >
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="mono text-[12px] text-[var(--ink-3)]">
                      {candidate.passage_id}
                    </span>
                    <span className="min-w-0 flex-1 text-[13px] leading-snug text-[var(--ink)]">
                      {candidate.title}
                    </span>
                    <span className="mono text-[12px] text-[var(--ink-3)]">
                      {candidate.doc} §{candidate.section}
                    </span>
                  </div>

                  <div className="mt-2">
                    <Meter
                      value={candidate.relevance}
                      height={3}
                      color={isGoverning ? "var(--ok)" : "rgba(255,255,255,0.32)"}
                    />
                  </div>

                  <div className="mt-3 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(190px,1fr))]">
                    <div>
                      <Label>The model proposed</Label>
                      <p className="mt-1 text-[12px] leading-snug text-[var(--ink-2)]">
                        {isGoverning
                          ? "This passage, as governing."
                          : rejection
                            ? `Rejected: ${rejection.why}`
                            : "Not selected."}
                      </p>
                    </div>
                    <div>
                      <Label className="flex items-center gap-2">
                        <span>The checker found</span>
                        <ClauseTally clauses={clausesById[candidate.passage_id] ?? []} />
                        <span
                          className="text-[11px] tracking-normal"
                          style={{ color: admissible ? "var(--ok)" : "var(--bad)" }}
                        >
                          {admissible ? (
                            <Term k="admissible">allowed</Term>
                          ) : (
                            "not allowed"
                          )}
                        </span>
                      </Label>
                      <div className="mt-2">
                        <ClauseVerdict clauses={clausesById[candidate.passage_id] ?? []} />
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
            {candidates.length === 0 ? (
              <li className="glass-2 px-4 py-3 text-[13px] text-[var(--ink-2)]">
                Retrieval was not invoked for this Situation.
              </li>
            ) : null}
          </ul>
        </Disclosure>

        <Disclosure
          summary="The orchestrated flow, step by step"
          hint="Coloured by the tier that ran each step, so the alternation between model and checker is visible at a glance"
        >
          <FlowTrack steps={flow} />
        </Disclosure>
      </div>
    </GlassCard>
  );
}
