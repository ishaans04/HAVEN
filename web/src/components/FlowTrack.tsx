"use client";

import { useState } from "react";
import type { AuditStep } from "@/lib/types";
import { Term } from "./Term";

const TIER_TONE: Record<string, string> = {
  deterministic: "var(--ok)",
  retrieval: "var(--info)",
  reasoning: "var(--iris)",
  orchestration: "var(--warn)",
  human: "var(--ink)",
};

const TIER_ORDER = ["deterministic", "retrieval", "reasoning", "orchestration"];

/**
 * The orchestrated flow, as a rail.
 *
 * It was a list: nine rows, each with a step name, a tier, a duration and a
 * sentence. Everything true and nothing visible, because the thing the flow
 * actually demonstrates is not in any single row — it is in the *sequence*.
 *
 * Colour the rail by tier and the architecture states itself: the model's
 * choice sits between a deterministic admissibility check and a deterministic
 * verify, and generation only happens downstream of both. That is the
 * propose/dispose invariant as a pattern you can see from across a room, and no
 * amount of per-row prose was ever going to say it.
 *
 * The summary line asserts only what the steps in hand actually show. An
 * earlier draft claimed the reasoning tier never runs twice in a row, which is
 * false here -- FUSE and GENERATE are consecutive reasoning steps. A console
 * whose case rests on not overclaiming cannot overclaim in its own caption.
 *
 * Durations are not encoded as width. Every step here runs in under a
 * millisecond, so proportional segments would render as noise pretending to be
 * data. They are read out instead, per step, on hover or focus.
 */
export function FlowTrack({ steps }: { steps: AuditStep[] }) {
  const [active, setActive] = useState<number | null>(null);

  if (!steps.length) return null;

  const total = steps.reduce((sum, s) => sum + s.duration_ms, 0);
  const tiersUsed = TIER_ORDER.filter((t) => steps.some((s) => s.tier === t));
  const deterministic = steps.filter((s) => s.tier === "deterministic").length;
  // Only mention the verify if a VERIFY step is actually in this flow, and say
  // "put to the checker" rather than "verified": on a refusal the checker is
  // what rejected the passage, and nothing was generated at all.
  const verifies = steps.some((s) => s.step === "VERIFY");
  const shown = active === null ? null : steps[active];

  return (
    <div className="glass-2 p-4">
      {/* The rail. */}
      <div className="flex items-end gap-1">
        {steps.map((step, i) => {
          const colour = TIER_TONE[step.tier] ?? "var(--ink-3)";
          const on = active === i;
          return (
            <button
              key={step.seq}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive((v) => (v === i ? null : v))}
              onFocus={() => setActive(i)}
              onBlur={() => setActive((v) => (v === i ? null : v))}
              className="group flex min-w-0 flex-1 flex-col items-stretch gap-1.5 rounded-[6px] pb-1 pt-2 text-left"
              aria-label={`Step ${i + 1}, ${step.step}, ${step.tier} tier, ${step.duration_ms.toFixed(1)} milliseconds. ${step.detail}`}
            >
              <span
                className="h-[6px] w-full rounded-full transition-all duration-200"
                style={{
                  background: colour,
                  opacity: active === null || on ? 1 : 0.42,
                  boxShadow: on ? `0 0 12px -2px ${colour}` : undefined,
                  transform: on ? "scaleY(1.5)" : undefined,
                }}
              />
              <span
                className="mono block truncate text-[11px] uppercase tracking-[0.06em] transition-colors"
                style={{ color: on ? colour : "var(--ink-3)" }}
              >
                {step.step.replace("SCHEDULE_IMPACT", "SCHEDULE").replace("GENERATE_FALLBACK", "FALLBACK")}
              </span>
            </button>
          );
        })}
      </div>

      {/* One readout, fixed height, so hovering the rail never moves the page. */}
      <div className="mt-3 min-h-[46px] border-t border-white/[0.07] pt-3">
        {shown ? (
          <>
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="mono text-[12px] font-medium text-[var(--ink)]">{shown.step}</span>
              <span
                className="text-[11px] uppercase tracking-[0.12em]"
                style={{ color: TIER_TONE[shown.tier] ?? "var(--ink-3)" }}
              >
                {shown.tier}
              </span>
              <span className="mono ml-auto text-[11px] text-[var(--ink-3)]">
                {shown.duration_ms.toFixed(1)} ms
              </span>
            </div>
            <p className="mt-1 text-[12px] leading-snug text-[var(--ink-2)]">{shown.detail}</p>
          </>
        ) : (
          <p className="text-[12px] leading-snug text-[var(--ink-3)]">
            {steps.length} step{steps.length === 1 ? "" : "s"} in {total.toFixed(1)} ms.{" "}
            {deterministic} of them were{" "}
            <Term k="deterministic">ordinary arithmetic</Term>.
            {verifies
              ? " The rule the AI picked went to the checker before it could be cited."
              : ""}{" "}
            Hover any segment to see what it did.
          </p>
        )}
      </div>

      {/* Which colour is which tier. */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {tiersUsed.map((tier) => (
          <span key={tier} className="flex items-center gap-1.5 text-[11px] text-[var(--ink-2)]">
            <span
              className="h-[3px] w-4 rounded-full"
              style={{ background: TIER_TONE[tier], boxShadow: `0 0 7px -1px ${TIER_TONE[tier]}` }}
            />
            {tier}
          </span>
        ))}
      </div>
    </div>
  );
}
