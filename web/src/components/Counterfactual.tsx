"use client";

import type {
  AuditRecord,
  Citation,
  ClauseDetail,
  RetrievedCandidate,
  Situation,
} from "@/lib/types";
import { useMotionOK, useReveal } from "@/lib/motion";
import { Label } from "./ui";

/**
 * What ranking by similarity alone would have done.
 *
 * This is the argument the whole architecture exists to make. The candidate set
 * carries a retrieval score for every passage. Sort by that score, take the top
 * one, cite it: that is the ordinary shape of a retrieval-augmented answer, and
 * it is a well-defined baseline rather than a guess about what some other
 * system would say.
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
 *
 * ## Why it is staged rather than written
 *
 * It used to be a paragraph. Sixty-odd words at 13px, inside a tinted box,
 * below the fold of a card called "how it decided" — the single most persuasive
 * fact the product owns, formatted exactly like a footnote and read like one.
 *
 * The fix is not more words, it is fewer. The confrontation is already there in
 * the data: a score of 1.000 on one side, a checker that threw it out on the
 * other, and a count of conditions that says why. Given a bar that fills to a
 * perfect score, a row of condition lamps and a rejection stamp landing across
 * them, a reader gets the whole argument before they have read a sentence — and
 * the sentence that remains is one line instead of four.
 *
 * The drama is bounded by honesty. The stamp says OVERRULED because the checker
 * overruled it; when the checker agrees, the same component says UPHELD in a
 * neutral tone and makes no claim at all. A case where the model was right is
 * not a disappointment to be dressed up.
 */

export type Verdict =
  | { kind: "agreed"; passageId: string; relevance: number; clauses: boolean[] }
  | {
      kind: "wrong-rule";
      passageId: string;
      relevance: number;
      clauses: boolean[];
      instead: Citation;
    }
  | {
      kind: "should-refuse";
      passageId: string;
      relevance: number;
      clauses: boolean[];
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
  // Carried through per clause rather than as a count, so the card can show
  // *which* conditions failed as lamps instead of asserting a total.
  const flags = topClauses.map((c) => c.satisfied);
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
      clauses: flags,
    };
  }

  if (!citation) return null;
  if (passed && top.passage_id === citation.passage_id) {
    return { kind: "agreed", passageId: top.passage_id, relevance: top.relevance, clauses: flags };
  }
  if (!passed) {
    return {
      kind: "wrong-rule",
      passageId: top.passage_id,
      relevance: top.relevance,
      clauses: flags,
      instead: citation,
    };
  }
  return null;
}

/**
 * The same comparison, straight from an evaluation and its audit record.
 *
 * The extraction is fiddly — the candidate list, the admissible set and the
 * clause tables each live in the `outputs` of a different audit step, and those
 * payloads are `Record<string, unknown>` on both sides of the contract. Having
 * two pages assert that shape independently is how they end up disagreeing
 * about the same evaluation, so both go through here.
 */
export function verdictFromAudit(
  situation: Situation | null | undefined,
  audit: AuditRecord | null | undefined,
): Verdict | null {
  if (!situation || !audit) return null;

  const step = (name: string) => audit.steps.find((s) => s.step === name);
  const admissibility = step("ADMISSIBILITY");

  return compareToSimilarity({
    candidates: (step("RETRIEVE")?.outputs.candidates ?? []) as RetrievedCandidate[],
    admissible: new Set((admissibility?.outputs.admissible ?? []) as string[]),
    clauses: (admissibility?.outputs.clauses ?? {}) as Record<string, ClauseDetail[]>,
    citation: situation.recommendation?.citation,
    outcome: situation.outcome,
    refusalReason: situation.refusal?.reason,
  });
}

/** Timings, in ms. One shared clock so the beats cannot drift apart. */
const T = { fill: 760, pips: 1180, stamp: 1620, tail: 1980 };

export function Counterfactual({ verdict }: { verdict: Verdict | null }) {
  // Hooks run before the early return: this component may legitimately render
  // nothing, and bailing above them would change the hook order between cases.
  const { ref, shown } = useReveal<HTMLDivElement>();
  const motionOK = useMotionOK();

  if (!verdict) return null;

  const diverged = verdict.kind !== "agreed";
  const colour = diverged ? "var(--warn)" : "var(--ok)";
  const failed = verdict.clauses.filter((c) => !c).length;
  const total = verdict.clauses.length;

  /**
   * Held at the first keyframe until the card is actually on screen.
   *
   * `both` fill plus `paused` renders an animation at its `from` state through
   * the delay, so the sequence waits rather than playing to an empty room —
   * this card sits a screen or two below the answer and would otherwise have
   * finished before the reader ever scrolled to it.
   */
  const playState = shown ? "running" : ("paused" as const);
  /**
   * Delays are zeroed when motion is off. The global reduced-motion reset
   * collapses `animation-duration` but says nothing about `animation-delay`,
   * so a 1.6s stamp cue would still leave the verdict blank for 1.6 seconds on
   * a machine that asked for no animation at all.
   */
  const at = (ms: number) => (motionOK ? ms : 0);

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-[var(--radius-sm)] p-4"
      style={{
        background: diverged
          ? "color-mix(in oklab, var(--warn) 7%, transparent)"
          : "rgba(255,255,255,0.03)",
        boxShadow: diverged
          ? "inset 0 0 0 1px color-mix(in oklab, var(--warn) 22%, transparent)"
          : "inset 0 0 0 1px rgba(255,255,255,0.07)",
      }}
    >
      <Label className="!text-[11px]">If the closest match had won</Label>

      <div className="mt-3 grid gap-x-5 gap-y-4 sm:grid-cols-[1fr_auto]">
        {/* The contender. A perfect score, drawn at the size of the claim it
            is making, so that striking it out means something. */}
        <div className="min-w-0">
          <div className="label !text-[11px] !tracking-[0.1em]">Ranked first by wording</div>
          <div className="mt-1.5 flex items-baseline gap-2.5">
            <span
              className="readout text-[30px] leading-none"
              style={{ color: diverged ? "var(--ink-2)" : "var(--ink)" }}
            >
              {verdict.relevance.toFixed(3)}
            </span>
            <span className="mono truncate text-[12px] text-[var(--ink-3)]">
              {verdict.passageId}
            </span>
          </div>

          {/* The score as a track. At 1.000 it fills completely, which is the
              whole point: nothing about the retrieval tier's own reading of
              this passage looked wrong. */}
          <div
            className="relative mt-2.5 h-[6px] w-full overflow-hidden rounded-full"
            style={{ background: "rgba(255,255,255,0.08)" }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max(0, Math.min(1, verdict.relevance)) * 100}%`,
                background: diverged
                  ? "linear-gradient(90deg, color-mix(in oklab, var(--warn) 35%, transparent), var(--warn))"
                  : "linear-gradient(90deg, color-mix(in oklab, var(--ok) 35%, transparent), var(--ok))",
                transformOrigin: "left",
                animation: `overrule-fill ${T.fill}ms cubic-bezier(0.16,1,0.3,1) both`,
                animationPlayState: playState,
              }}
            />
            {/* Struck through, in time with the stamp. */}
            {diverged ? (
              <div
                className="absolute inset-y-0 left-0 w-full"
                style={{
                  transformOrigin: "left",
                  animation: `overrule-strike 420ms cubic-bezier(0.16,1,0.3,1) ${at(T.stamp)}ms both`,
                  animationPlayState: playState,
                  background:
                    "linear-gradient(transparent calc(50% - 1px), var(--void-deep) calc(50% - 1px), var(--void-deep) calc(50% + 1px), transparent calc(50% + 1px))",
                }}
              />
            ) : null}
          </div>
        </div>

        {/* The checker. Lamps, not prose: one per condition, and the failures
            are the only thing carrying colour. */}
        <div className="min-w-0 sm:text-right">
          <div className="label !text-[11px] !tracking-[0.1em]">Deterministic check</div>

          {total > 0 ? (
            <div className="mt-2 flex items-center gap-1.5 sm:justify-end">
              {verdict.clauses.map((ok, i) => (
                <span
                  key={i}
                  className="h-[9px] w-[9px] rounded-full"
                  style={{
                    background: ok ? "color-mix(in oklab, var(--ok) 45%, transparent)" : colour,
                    boxShadow: ok ? "none" : `0 0 9px -1px ${colour}`,
                    animation: `overrule-pip 320ms cubic-bezier(0.16,1,0.3,1) ${at(T.pips + i * 90)}ms both`,
                    animationPlayState: playState,
                  }}
                />
              ))}
            </div>
          ) : null}

          <div
            className="mt-2 text-[12px] leading-snug"
            style={{
              color: diverged ? colour : "var(--ink-2)",
              animation: `overrule-rise 380ms ease-out ${at(T.pips + total * 90)}ms both`,
              animationPlayState: playState,
            }}
          >
            {total === 0
              ? diverged
                ? "no conditions met"
                : "no conditions to check"
              : diverged
                ? `${failed} of ${total} conditions failed`
                : `all ${total} conditions met`}
          </div>
        </div>
      </div>

      {/* The verdict, landing across the two. */}
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-white/[0.09] pt-3">
        <span
          className="label !text-[12px] !tracking-[0.18em]"
          style={{
            color: colour,
            animation: `overrule-stamp 520ms cubic-bezier(0.34,1.56,0.64,1) ${at(T.stamp)}ms both`,
            animationPlayState: playState,
          }}
        >
          {diverged ? "Overruled" : "Upheld"}
        </span>

        <span
          className="min-w-0 flex-1 text-[12px] leading-snug text-[var(--ink-2)]"
          style={{
            animation: `overrule-rise 420ms ease-out ${at(T.tail)}ms both`,
            animationPlayState: playState,
          }}
        >
          {verdict.kind === "wrong-rule" ? (
            <>
              Applies instead{" "}
              <span className="mono text-[var(--ok)]">
                {verdict.instead.doc} §{verdict.instead.section}
              </span>
            </>
          ) : verdict.kind === "should-refuse" ? (
            <>Nothing else applied either, so HAVEN refused.</>
          ) : (
            <>Closest and correct were the same rule this time.</>
          )}
        </span>
      </div>

      {/* One line of consequence, where there used to be four. */}
      {diverged ? (
        <p
          className="mt-2.5 text-[12px] leading-snug text-[var(--ink-3)]"
          style={{
            animation: `overrule-rise 420ms ease-out ${at(T.tail + 140)}ms both`,
            animationPlayState: playState,
          }}
        >
          {verdict.kind === "should-refuse"
            ? "Ranking by similarity alone would have answered this with a real section number, for a situation no rule covers."
            : "Ranking by similarity alone would have cited the wrong rule, with a perfect score behind it."}
        </p>
      ) : null}
    </div>
  );
}
