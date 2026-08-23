"use client";

import type { ReactNode } from "react";
import {
  Ban,
  FileSearch,
  Gavel,
  PlugZap,
  Scale,
  SignalLow,
  Sigma,
  UsersRound,
} from "lucide-react";
import type { Refusal, Situation } from "@/lib/types";
import { Chip, Label, Meter } from "./ui";

/**
 * Why HAVEN stopped.
 *
 * The product's own documents call refusal "the single most important behaviour
 * in the whole system" and "the primary demonstration of judgement". The
 * contract backs that up: there are seven distinct reasons the flow can decline,
 * and they are not variations on a theme. "No rule covers this" is a statement
 * about the rulebook. "The input is too thin" is a statement about the data.
 * "The model and the checker disagreed" is a statement about the architecture
 * catching itself. Rendering all seven as one generic red card throws away the
 * distinction the system worked hardest to make.
 *
 * So each reason gets its own icon, its own plain sentence, and — the part that
 * matters — its own evidence. The thing that makes a refusal credible is
 * different every time: for a missing rule it is the set of documents that were
 * searched and came back empty; for thin input it is the coverage figure; for a
 * disagreement it is both verdicts side by side.
 *
 * Everything here comes off the `Refusal` object and the `Situation` that
 * carries it. Nothing is inferred, and any reason not in the map still renders —
 * with the generic treatment rather than with nothing.
 */

interface Kind {
  icon: ReactNode;
  /** What happened, in one plain clause. */
  what: string;
  /** What HAVEN did about it. */
  did: string;
}

const KINDS: Record<string, Kind> = {
  no_governing_procedure: {
    icon: <FileSearch size={15} />,
    what: "Every rule in the book was checked. None of them covers this situation.",
    did: "Rather than reach for the nearest plausible rule, HAVEN stopped and handed the decision up.",
  },
  insufficient_input: {
    icon: <SignalLow size={15} />,
    what: "There is not enough sleep and duty history for this operator to score them confidently.",
    did: "The recommendation was withheld rather than issued at false confidence.",
  },
  roster_conflict: {
    icon: <UsersRound size={15} />,
    what: "Every fix would have left a safety-critical role unstaffed.",
    did: "The schedule-impact screen blocked it, because a fix that breaks the roster is not a fix.",
  },
  provider_unavailable: {
    icon: <PlugZap size={15} />,
    what: "The reasoning tier could not be reached.",
    did: "Deterministic scoring is unaffected. But no rule can be interpreted without the reasoning tier, so the Situation escalates rather than being answered from the numbers alone.",
  },
  precondition_unmet: {
    icon: <Gavel size={15} />,
    what: "The rule the AI picked does not meet its own stated conditions.",
    did: "The checker rejected it. A citation the checker will not stand behind is never shown to an operator.",
  },
  checker_model_disagreement: {
    icon: <Scale size={15} />,
    what: "The reasoning tier and the deterministic checker reached different conclusions.",
    did: "Resolved by refusing. Disagreement fails closed in both directions: a rejected passage is never cited, and a refusal is never overridden upward.",
  },
  numeric_integrity_failure: {
    icon: <Sigma size={15} />,
    what: "A safety figure in the draft did not match what the maths computed.",
    did: "The output was discarded. The maths owns the numbers, and a number that drifted is a failed draft, not a rounding difference.",
  },
};

const GENERIC: Kind = {
  icon: <Ban size={15} />,
  what: "The flow reached a state it will not answer from.",
  did: "The Situation was escalated to a human rather than resolved automatically.",
};

const humanise = (value: string) => value.replace(/_/g, " ");

export function RefusalBlock({
  refusal,
  situation,
}: {
  refusal: Refusal;
  situation: Situation;
}) {
  const kind = KINDS[refusal.reason] ?? GENERIC;

  return (
    <div
      className="mt-5 overflow-hidden rounded-[var(--radius-sm)]"
      style={{
        background: "color-mix(in oklab, var(--bad) 6%, transparent)",
        boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--bad) 26%, transparent)",
      }}
    >
      {/* Why it stopped. */}
      <div className="flex items-start gap-3 p-4">
        <span
          className="mt-[1px] shrink-0 rounded-full p-2"
          style={{ color: "var(--bad)", background: "color-mix(in oklab, var(--bad) 12%, transparent)" }}
        >
          {kind.icon}
        </span>
        <div className="min-w-0 flex-1">
          <Label className="!text-[11px]" >Why it stopped</Label>
          <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink)]">{kind.what}</p>
          <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-2)]">{kind.did}</p>
        </div>
      </div>

      <Evidence refusal={refusal} situation={situation} />
    </div>
  );
}

/**
 * The evidence that makes this particular refusal credible.
 *
 * Chosen by reason rather than shown all at once. A reader asking "why should I
 * believe it looked properly?" is asking a different question for each kind of
 * stop, and answering all seven at once answers none of them.
 */
function Evidence({ refusal, situation }: { refusal: Refusal; situation: Situation }) {
  const coverage = situation.evidence.data_coverage;

  switch (refusal.reason) {
    case "no_governing_procedure":
      return refusal.searched.length ? (
        <Panel>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="readout text-[26px] leading-none text-[var(--ink)]">
              {refusal.searched.length}
            </span>
            <span className="text-[13px] text-[var(--ink-2)]">
              document{refusal.searched.length === 1 ? "" : "s"} searched
            </span>
            <span className="readout ml-auto text-[13px]" style={{ color: "var(--bad)" }}>
              none applied
            </span>
          </div>
          <div className="mono mt-3 flex flex-wrap gap-1.5">
            {refusal.searched.map((doc) => (
              <span
                key={doc}
                className="rounded-full px-2.5 py-[3px] text-[11px] text-[var(--ink-3)] line-through"
                style={{ background: "rgba(255,255,255,0.05)" }}
              >
                {doc}
              </span>
            ))}
          </div>
          {refusal.best_candidate ? (
            <div className="mt-4 border-t border-white/[0.07] pt-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-[13px] text-[var(--ink-2)]">
                  Closest was {refusal.best_candidate.doc} §{refusal.best_candidate.section}
                </span>
                <span className="mono text-[11px] text-[var(--ink-3)]">
                  similarity {refusal.best_candidate.relevance.toFixed(3)}
                </span>
              </div>
              <div className="mt-2">
                <Meter
                  value={refusal.best_candidate.relevance}
                  threshold={refusal.gate}
                  color="var(--bad)"
                  height={4}
                />
              </div>
              <p className="mt-2 text-[12px] leading-snug text-[var(--ink-3)]">
                Being the closest match is not the same as applying. That was settled condition by
                condition, not by this number.
              </p>
            </div>
          ) : null}
        </Panel>
      ) : null;

    case "insufficient_input":
      return (
        <Panel>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="readout text-[26px] leading-none" style={{ color: "var(--bad)" }}>
              {Math.round(coverage * 100)}%
            </span>
            <span className="text-[13px] text-[var(--ink-2)]">of the expected record present</span>
            <Chip tone="bad" className="ml-auto">
              confidence {situation.confidence}
            </Chip>
          </div>
          <div className="mt-3">
            <Meter value={coverage} color="var(--bad)" height={4} />
          </div>
          <p className="mt-2 text-[12px] leading-snug text-[var(--ink-3)]">
            The deterministic tier still scored the window, and those figures above are real. What
            it will not do is attach a recommendation to them at this coverage.
          </p>
        </Panel>
      );

    case "precondition_unmet":
    case "checker_model_disagreement":
      return refusal.failed_clauses.length ? (
        <Panel>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <Label className="!text-[11px]">
              {refusal.model_selected
                ? `The checker rejected ${refusal.model_selected}`
                : "Unsatisfied preconditions"}
            </Label>
            <span className="readout ml-auto text-[13px]" style={{ color: "var(--bad)" }}>
              {refusal.failed_clauses.length} unmet
            </span>
          </div>
          <ul className="mt-3 space-y-2">
            {refusal.failed_clauses.map((clause) => (
              <li key={clause.clause} className="text-[13px] leading-snug">
                <span className="mono text-[12px] text-[var(--ink-2)]">{clause.clause}</span>
                <span className="ml-2 text-[var(--ink-3)]">
                  wants {clause.expected} · got {clause.actual}
                </span>
                <div className="mt-1 text-[var(--bad)]">{clause.explanation}</div>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null;

    case "provider_unavailable":
      return (
        <Panel>
          <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(190px,1fr))]">
            <div>
              <Label className="!text-[11px]">Still running</Label>
              <p className="mt-2 text-[13px] leading-snug text-[var(--ink-2)]">
                Three-Process Model and NASA-TLX scoring, the deterministic screens, and the audit
                trail. Every figure above was computed normally.
              </p>
            </div>
            <div>
              <Label className="!text-[11px]">Unavailable</Label>
              <p className="mt-2 text-[13px] leading-snug text-[var(--bad)]">
                Procedure interpretation. Without it nothing can be cited, and an uncited
                recommendation is one this system will not show.
              </p>
            </div>
          </div>
        </Panel>
      );

    case "roster_conflict":
      return (
        <Panel>
          <p className="text-[13px] leading-relaxed text-[var(--ink-2)]">
            A recommendation that pulls this operator would leave a safety-critical role without
            somebody qualified and rested to fill it. The roster check below shows the state it
            would have left behind.
          </p>
        </Panel>
      );

    default:
      return null;
  }
}

function Panel({ children }: { children: ReactNode }) {
  return (
    <div
      className="p-4"
      style={{
        background: "rgba(0,0,0,0.18)",
        boxShadow: "inset 0 1px 0 color-mix(in oklab, var(--bad) 16%, transparent)",
      }}
    >
      {children}
    </div>
  );
}

/** The escalation target, as the action it is. */
export function EscalationTarget({ refusal }: { refusal: Refusal }) {
  return (
    <span className="text-[13px] text-[var(--ink-2)]">
      Escalates to{" "}
      <span className="font-medium text-[var(--bad)]">{humanise(refusal.escalate_to)}</span>
    </span>
  );
}
