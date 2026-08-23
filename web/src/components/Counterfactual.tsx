"use client";

import { AlertTriangle, Check, ShieldAlert } from "lucide-react";
import type { Citation } from "@/lib/types";
import { Term } from "./Term";
import { Label } from "./ui";

/**
 * What ranking by similarity alone would have done.
 *
 * This is the argument the whole architecture exists to make, and until now the
 * console never made it. The candidate set carries a retrieval score for every
 * passage. Sort by that score, take the top one, cite it: that is the ordinary
 * shape of a retrieval-augmented answer, and it is a well-defined baseline
 * rather than a guess about what some other system would say.
 *
 * On this corpus that baseline is wrong twice.
 *
 *   eva_near_miss   top score 1.000 on a passage the checker rejects 3/4.
 *                   The rule that actually governs is a different section.
 *   no_procedure    top score 1.000, rejected 3/4, and nothing governs the
 *                   situation at all — the correct output is to refuse.
 *
 * A perfect similarity score on the wrong rule is not a freak result, it is the
 * designed behaviour of a corpus with near-misses in it: passages that share the
 * governing rule's vocabulary almost word for word are *supposed* to rank
 * alongside it. Retrieval gets you a shortlist. It was never evidence.
 *
 * The claim is deliberately narrow. It says what the top-ranked passage was and
 * what the checker did with it. It does not claim what a language model would
 * have said, because nothing here ran that experiment.
 */

export type Verdict =
  | { kind: "agreed"; passageId: string; relevance: number }
  | {
      kind: "wrong-rule";
      passageId: string;
      relevance: number;
      met: number;
      total: number;
      instead: Citation;
    }
  | {
      kind: "should-refuse";
      passageId: string;
      relevance: number;
      met: number;
      total: number;
    };

/**
 * Work out which of the three the current evaluation is.
 *
 * Returns null when there is nothing to compare — retrieval never ran, or the
 * refusal came from somewhere other than the rulebook, in which case a claim
 * about ranking would be beside the point.
 */
export function compareToSimilarity({
  candidates,
  admissible,
  clauses,
  citation,
  outcome,
  refusalReason,
}: {
  candidates: { passage_id: string; relevance: number }[];
  admissible: Set<string>;
  clauses: Record<string, { satisfied: boolean }[]>;
  citation: Citation | null | undefined;
  outcome: string;
  refusalReason: string | null | undefined;
}): Verdict | null {
  if (!candidates.length) return null;

  const top = [...candidates].sort((a, b) => b.relevance - a.relevance)[0];
  const topClauses = clauses[top.passage_id] ?? [];
  const met = topClauses.filter((c) => c.satisfied).length;
  const passed = admissible.has(top.passage_id);

  if (outcome === "refusal") {
    // Only interesting when the rulebook is what ran out. A provider outage
    // refuses for reasons that have nothing to do with ranking.
    if (refusalReason !== "no_governing_procedure") return null;
    if (passed) return null;
    return {
      kind: "should-refuse",
      passageId: top.passage_id,
      relevance: top.relevance,
      met,
      total: topClauses.length,
    };
  }

  if (!citation) return null;
  if (passed && top.passage_id === citation.passage_id) {
    return { kind: "agreed", passageId: top.passage_id, relevance: top.relevance };
  }
  if (!passed) {
    return {
      kind: "wrong-rule",
      passageId: top.passage_id,
      relevance: top.relevance,
      met,
      total: topClauses.length,
      instead: citation,
    };
  }
  return null;
}

export function Counterfactual({ verdict }: { verdict: Verdict | null }) {
  if (!verdict) return null;

  const diverged = verdict.kind !== "agreed";
  const colour = diverged ? "var(--warn)" : "var(--ok)";

  return (
    <div
      className="rounded-[var(--radius-sm)] p-4"
      style={{
        background: diverged ? "color-mix(in oklab, var(--warn) 7%, transparent)" : "rgba(255,255,255,0.04)",
        boxShadow: `inset 0 0 0 1px ${diverged ? "color-mix(in oklab, var(--warn) 28%, transparent)" : "rgba(255,255,255,0.06)"}`,
      }}
    >
      <div className="flex items-start gap-3">
        <span
          className="mt-[1px] shrink-0 rounded-full p-1.5"
          style={{ color: colour, background: diverged ? "color-mix(in oklab, var(--warn) 12%, transparent)" : "rgba(255,255,255,0.06)" }}
        >
          {verdict.kind === "should-refuse" ? (
            <ShieldAlert size={14} />
          ) : diverged ? (
            <AlertTriangle size={14} />
          ) : (
            <Check size={14} />
          )}
        </span>

        <div className="min-w-0 flex-1">
          <Label className="!text-[11px]">If the closest match had won</Label>

          <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink)]">
            The closest match by wording was{" "}
            <span className="mono">{verdict.passageId}</span> at{" "}
            <span className="readout" style={{ color: diverged ? colour : "var(--ink)" }}>
              {verdict.relevance.toFixed(3)}
            </span>
            {verdict.kind === "agreed" ? (
              <>
                , and the <Term k="checker">checker</Term> allowed it. Closest and correct were
                the same rule this time.
              </>
            ) : verdict.kind === "wrong-rule" ? (
              <>
                . It failed{" "}
                <span className="readout" style={{ color: colour }}>
                  {verdict.total - verdict.met} of its {verdict.total}
                </span>{" "}
                <Term k="preconditions">conditions</Term>, and one failure is enough. The rule
                that actually applies is{" "}
                <span className="mono text-[var(--ok)]">
                  {verdict.instead.doc} §{verdict.instead.section}
                </span>
                .
              </>
            ) : (
              <>
                . It failed{" "}
                <span className="readout" style={{ color: colour }}>
                  {verdict.total - verdict.met} of its {verdict.total}
                </span>{" "}
                <Term k="preconditions">conditions</Term>, and one failure is enough. Nothing
                else applied either, so the right answer was to refuse.
              </>
            )}
          </p>

          {diverged ? (
            <p className="mt-2 text-[12px] leading-snug text-[var(--ink-2)]">
              {verdict.kind === "should-refuse"
                ? "A system that just cites its best match would have answered this with a real section number, from a real document, for a situation no rule covers. A wrong answer that checks out is worse than no answer, and preventing it is what the checker is for."
                : "A system that just cites its best match would have named the wrong rule here, with a perfect-looking score behind it."}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
