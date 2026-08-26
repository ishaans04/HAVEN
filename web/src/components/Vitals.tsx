"use client";

import type { Situation } from "@/lib/types";
import { Field, Label, TONE_VAR } from "./ui";

/**
 * The four figures, as one reading.
 *
 * They were four equal boxes, which gave the KSS footnote the same weight as
 * the only fact that decides anything: alertness sits at 0.69 against a line of
 * 0.70. Equal weight is a claim, and it was the wrong one.
 *
 * So alertness gets the track, with the threshold drawn on it. You can see the
 * miss without reading a digit, which is the whole point for a reader meeting
 * this screen for the first time. Workload, hours awake and the body clock sit
 * under it as a register — named, unboxed, and each carrying the instrument it
 * was read off.
 */
export function Vitals({ situation }: { situation: Situation }) {
  const score = situation.alertness_score;
  const threshold = situation.recommendation?.projection?.threshold ?? 0.7;
  const below = score < threshold;
  const tone = score < 0.6 ? "bad" : below ? "warn" : "ok";
  const colour = TONE_VAR[tone];
  const gap = Math.abs(threshold - score);

  return (
    <div className="divide-top pt-4">
      {/* The reading that decides. */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="readout text-[38px] leading-none" style={{ color: colour }}>
          {score.toFixed(2)}
        </span>
        <Label className="!text-[11px]">alertness</Label>
        <span className="ml-auto text-[12px]" style={{ color: colour }}>
          {gap < 0.005
            ? "on the line"
            : `${gap.toFixed(2)} ${below ? "below" : "above"} the line`}
        </span>
      </div>

      <div className="relative mt-3 h-2.5 rounded-full" style={{ background: "rgba(255,255,255,0.07)" }}>
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out"
          style={{
            width: `${Math.max(0, Math.min(100, score * 100))}%`,
            background: `linear-gradient(90deg, color-mix(in oklab, ${colour} 35%, transparent), ${colour})`,
            boxShadow: `0 0 14px -3px ${colour}`,
          }}
        />
        {/* The threshold, as a notch through the track rather than a line over
            it — the reading either reaches it or it does not. */}
        <div
          className="absolute -top-1.5 -bottom-1.5 w-[2px] rounded-full bg-[var(--ink)]"
          style={{ left: `${Math.min(100, threshold * 100)}%` }}
        />
        <span
          className="mono absolute -top-[22px] whitespace-nowrap text-[11px] text-[var(--ink-2)]"
          style={{ left: `${Math.min(100, threshold * 100)}%`, transform: "translateX(-50%)" }}
        >
          {threshold.toFixed(2)} execution threshold
        </span>
      </div>

      {/* Everything else, at the size it deserves.

          This was three filled boxes, each with a small ring gauge and an icon
          inside it — nested panels of exactly the kind the unboxing pass took
          the card count from 42 down to 3 to be rid of, and a ring apiece on
          top.

          Two of those rings were quantities divided by an arbitrary ceiling
          (hours awake over an assumed 18) and the third was not a quantity at
          all: "body clock clear" was drawn as 18% of a ring, a number that
          exists nowhere in the engine and means nothing. Rendering an invented
          figure as a gauge is the precise thing `lib/ask.ts` exists to prevent,
          done in pixels instead of words.

          So the ring goes and the provenance arrives. Each figure now names the
          instrument it came off — NASA-TLX, the sleep debt behind the hours,
          the Karolinska score behind the verdict — which had been sitting in a
          `title` attribute all along, reachable by hover on a desktop and by
          nothing at all on a touch screen. */}
      <dl className="mt-5 flex flex-wrap gap-x-7 gap-y-4">
        <Field
          label="Workload"
          note={`NASA-TLX · ${situation.evidence.workload_band.replace(/_/g, " ")}`}
        >
          <span className="readout text-[15px] text-[var(--ink)]">
            {situation.workload_score.toFixed(0)}
          </span>
        </Field>
        <Field
          label="Awake"
          note={`sleep debt ${situation.evidence.sleep_debt_h.toFixed(1)} h`}
        >
          <span
            className="readout text-[15px]"
            style={{
              color: situation.evidence.hours_awake > 12 ? "var(--warn)" : "var(--ink)",
            }}
          >
            {situation.evidence.hours_awake.toFixed(1)}h
          </span>
        </Field>
        <Field label="Body clock" note={`KSS ${situation.evidence.kss.toFixed(1)}`}>
          <span
            className="text-[15px]"
            style={{ color: situation.circadian_flag ? "var(--bad)" : "var(--ink)" }}
          >
            {situation.circadian_flag ? "In the trough" : "Clear"}
          </span>
        </Field>
      </dl>
    </div>
  );
}
