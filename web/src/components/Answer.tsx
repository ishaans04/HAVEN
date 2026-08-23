"use client";

import { ShieldAlert } from "lucide-react";
import type { Situation } from "@/lib/types";
import { answerFor, questionFor } from "@/lib/ask";
import { Chip, TONE_VAR, toneOf, utcTime } from "./ui";

/**
 * The consultation.
 *
 * One question, one answer, at the size of the claim being made. Everything
 * else on the page is evidence for this and is sequenced underneath it.
 *
 * The previous card put the recommendation inside a header, two chips, a
 * label and a monospace identifier line, at 34px — visually the fourth thing
 * you met rather than the first. A consultation does not open by reciting the
 * patient's record number.
 *
 * On a refusal the whole block changes register. That is not decoration: a
 * refusal is a different kind of answer, and the single most distinctive thing
 * this system does is decline to answer when nothing in the rulebook covers
 * the case. It should feel like the machine stopping, not like an error.
 */
export function Answer({ situation }: { situation: Situation | null }) {
  const answer = answerFor(situation);
  const question = questionFor(situation);
  const colour = TONE_VAR[answer.tone];

  if (!situation) {
    return (
      <div className="max-w-2xl">
        <h1 className="display text-[26px] leading-[1.12] tracking-[-0.03em] sm:text-[34px]">
          {question}
        </h1>
        <p
          className="display mt-5 text-[38px] leading-[1.02] tracking-[-0.04em] sm:text-[56px]"
          style={{ color: "var(--ok)" }}
        >
          Nobody.
        </p>
        <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-[var(--ink-2)]">
          Every task in this window came through on the numbers alone. Nothing crossed a
          threshold, so HAVEN raised nothing. A quiet console is a working one.
        </p>
      </div>
    );
  }

  const isRefusal = answer.kind === "refusal";
  const rec = situation.recommendation;
  const ref = situation.refusal;
  const projection = rec?.projection ?? null;
  const riskTone = toneOf(situation.risk_level);

  return (
    <div className="max-w-2xl">
      {/* Who, what, when. Small, because it is context rather than content. */}
      <p className="mono text-[12px] text-[var(--ink-3)]">
        {situation.crew_member_name} · {situation.task_label} ·{" "}
        {utcTime(situation.task_scheduled)}
      </p>

      <h1 className="display mt-3 text-[26px] leading-[1.12] tracking-[-0.03em] sm:text-[34px]">
        {question}
      </h1>

      {/* The answer. */}
      <div className="mt-6 flex items-start gap-3">
        {isRefusal ? (
          <ShieldAlert
            size={30}
            className="mt-2 shrink-0 sm:mt-3"
            style={{ color: colour }}
          />
        ) : null}
        <p
          className="display text-[38px] leading-[1.02] tracking-[-0.04em] sm:text-[56px]"
          style={{ color: colour }}
        >
          {answer.headline}
        </p>
      </div>

      {/* The engine's own term, always travelling with the plain words. */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Chip tone={answer.tone} solid>
          {answer.precise}
        </Chip>
        <Chip tone={riskTone}>{situation.risk_level} risk</Chip>
        {rec ? (
          <Chip tone="info">
            {rec.citation.doc} §{rec.citation.section}
          </Chip>
        ) : null}
      </div>

      {/* One sentence. */}
      <p className="mt-5 text-[16px] leading-relaxed text-[var(--ink-2)]">
        {isRefusal ? (
          ref?.explanation
        ) : (
          <>
            <span className="text-[var(--ink)]">{situation.crew_member_name}</span> is predicted
            at{" "}
            <span className="readout text-[16px]" style={{ color: TONE_VAR[riskTone] }}>
              {situation.alertness_score.toFixed(2)}
            </span>{" "}
            alertness
            {projection ? (
              <>
                {" "}
                against a line of{" "}
                <span className="readout text-[16px]">{projection.threshold.toFixed(2)}</span>{" "}
                for this job
              </>
            ) : null}
            , with {situation.task_criticality} criticality
            {situation.circadian_flag ? ", inside their body-clock low" : ""}.
          </>
        )}
      </p>
    </div>
  );
}
