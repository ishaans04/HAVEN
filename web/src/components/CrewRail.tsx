"use client";

import { TrendingDown } from "lucide-react";
import type { CrewReadiness } from "@/lib/types";
import { signal } from "@/lib/coach";
import { Chip, TONE_VAR, toneOf } from "./ui";

/**
 * Zone 1 — Readiness Overview, reduced to what a scan needs.
 *
 * v1 put six numbers on every one of six crew cards: alertness, baseline,
 * delta, TLX, sleep debt, hours awake, window minimum, and the time the record
 * was read. Thirty-odd figures, all at 10px, none of them the question being
 * asked at this altitude — which is only ever "who here is running low?"
 *
 * So the roster carries one reading per person. The rest is intact and one
 * click away, under "the numbers", where somebody who wants the trailing sleep
 * debt to one decimal place can have it.
 *
 * ## Why this stopped being a rail of dials
 *
 * It was six ring gauges on six rounded cards in a horizontal scroller, and
 * both halves of that fought the one question the section exists to answer.
 *
 * **A ring cannot be compared to the ring beside it.** Judging "who is lowest"
 * from six arcs means comparing angles across six separated circles, which is
 * near the bottom of every ranking of how accurately people read a quantity.
 * Length against a common baseline is at the top. The old docstring argued a
 * dial "invites reading the state" — true of *one* dial, and the opposite of
 * what a rail of six needs, which is precisely a comparison. Bars on one shared
 * scale put the low operator in front of you before you have read a digit.
 *
 * **A scroller hides the answer.** Six operators at 186px each in a sidebar
 * showed three. If the question is who is running low and the low one is
 * off-screen, the component has failed at its only job — and nothing on screen
 * says there is more to see. Every operator is now visible at once.
 *
 * The notch stays: it is the operator's own baseline, and it is the difference
 * between a bar that reports a number and one that reports a departure. ".37"
 * means nothing until you can see it sitting well inside where that person
 * normally runs.
 */
export function CrewRail({
  readiness,
  selected,
  onSelect,
}: {
  readiness: CrewReadiness[];
  selected: string | null;
  onSelect: (crewId: string) => void;
}) {
  return (
    <ul className="w-full">
      {readiness.map((crew) => {
        const active = crew.crew_member === selected;
        const tone = toneOf(crew.status);
        const colour = TONE_VAR[tone];
        const pct = (v: number) => `${Math.max(0, Math.min(1, v)) * 100}%`;
        return (
          <li key={crew.crew_member} className="border-b border-white/[0.055] last:border-b-0">
            <button
              onClick={() => {
                onSelect(crew.crew_member);
                signal("crew");
              }}
              aria-pressed={active}
              className="group flex w-full items-center gap-3 py-2 pl-3 pr-1 text-left transition-colors"
              style={{
                // Selection is weight, not hue — see the note on `.selectable`
                // in globals.css. A rule down the left edge marks the chosen
                // row the way a roster marks one, without a box around it.
                background: active ? "rgba(255,255,255,0.055)" : undefined,
                boxShadow: active ? "inset 2px 0 0 0 var(--ink-2)" : undefined,
              }}
            >
              <span className="flex min-w-0 flex-[1.1] items-center gap-1.5">
                <span className="truncate text-[13px] font-medium tracking-[-0.005em] text-[var(--ink)]">
                  {crew.name}
                </span>
                {crew.trend === "declining" ? (
                  <TrendingDown size={12} aria-hidden className="shrink-0 text-[var(--bad)]" />
                ) : null}
              </span>

              {/* Shown at every width and allowed to truncate, rather than
                  dropped below a breakpoint: the column this sits in is far
                  narrower than the viewport, so a viewport media query hid the
                  role on a row that had room to spare for it. */}
              <span className="min-w-0 flex-1 truncate text-[11px] font-medium uppercase tracking-[0.11em] text-[var(--ink-3)]">
                {crew.role.replace(/_/g, " ")}
              </span>

              {/* The reading, on a scale shared with every other row. Longer is
                  strictly better here — the whole value of a common baseline is
                  in how finely two rows can be told apart along it. */}
              <span
                aria-hidden
                className="relative h-[5px] w-[72px] shrink-0 overflow-hidden rounded-full sm:w-[104px]"
                style={{ background: "rgba(255,255,255,0.08)" }}
              >
                <span
                  className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out"
                  style={{
                    width: pct(crew.alertness_score),
                    background: colour,
                    boxShadow: `0 0 10px -3px ${colour}`,
                  }}
                />
                {/* The operator's own baseline, cut through rather than drawn
                    over, so it reads as a graduation on the scale. */}
                <span
                  className="absolute top-0 h-full w-[1.5px]"
                  style={{
                    left: pct(crew.baseline_alertness),
                    background: "var(--void-deep)",
                    boxShadow: "0 0 0 0.5px rgba(255,255,255,0.35)",
                  }}
                />
              </span>

              <span
                className="readout w-[34px] shrink-0 text-right text-[13px]"
                style={{ color: colour }}
              >
                {crew.alertness_score.toFixed(2).slice(1)}
              </span>

              {/* Bar length and colour carry the state visually and carry
                  nothing at all to a screen reader. This is the same
                  information in the channel that does not depend on seeing it. */}
              <span className="sr-only">
                alertness {crew.alertness_score.toFixed(2)}, baseline{" "}
                {crew.baseline_alertness.toFixed(2)}, {crew.status}
                {crew.trend === "declining" ? ", declining" : ""}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * The same roster, with every figure v1 showed.
 *
 * Kept whole and moved behind a disclosure. Simplifying the first read is not
 * the same as removing the evidence, and the evidence is what makes a
 * deterministic tier worth having.
 */
export function CrewDetail({ readiness }: { readiness: CrewReadiness[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-[13px]">
        <thead>
          <tr className="label border-b border-white/10 [&>th]:px-3 [&>th]:pb-2 [&>th]:font-medium">
            <th className="!text-left">Operator</th>
            <th>Alertness</th>
            <th>Baseline</th>
            <th>TLX</th>
            <th>Sleep debt</th>
            <th>Awake</th>
            <th>Window low</th>
            <th>Record</th>
          </tr>
        </thead>
        <tbody className="text-[var(--ink-2)]">
          {readiness.map((crew) => (
            <tr key={crew.crew_member} className="border-b border-white/[0.055] last:border-0">
              <td className="px-3 py-2.5">
                <span className="block text-[var(--ink)]">{crew.name}</span>
                <span className="mono text-[11px] text-[var(--ink-3)]">
                  {crew.crew_member} · {crew.role.replace(/_/g, " ")}
                </span>
              </td>
              <td className="readout px-3" style={{ color: `var(--${crew.status === "nominal" ? "ok" : crew.status === "watch" ? "warn" : "bad"})` }}>
                {crew.alertness_score.toFixed(2)}
              </td>
              <td className="readout px-3">
                {crew.baseline_alertness.toFixed(2)}
                <span
                  className="ml-2 text-[11px]"
                  style={{
                    color:
                      crew.delta_vs_baseline <= -0.06
                        ? "var(--bad)"
                        : crew.delta_vs_baseline >= 0.02
                          ? "var(--ok)"
                          : "var(--ink-3)",
                  }}
                >
                  {crew.delta_vs_baseline >= 0 ? "+" : ""}
                  {crew.delta_vs_baseline.toFixed(2)}
                </span>
              </td>
              <td className="readout px-3">{crew.workload_score.toFixed(0)}</td>
              <td className="readout px-3">{crew.sleep_debt_h.toFixed(1)}h</td>
              <td className="readout px-3">{crew.hours_awake.toFixed(1)}h</td>
              <td className="readout px-3">
                {crew.window_min_alertness.toFixed(2)}
                <span className="mono ml-2 text-[11px] text-[var(--ink-3)]">
                  {new Date(crew.window_min_at).toISOString().slice(11, 16)}Z
                </span>
              </td>
              <td className="px-3">
                {crew.confidence === "insufficient" || crew.confidence === "low" ? (
                  <Chip tone="warn">{Math.round(crew.data_coverage * 100)}% coverage</Chip>
                ) : (
                  <span className="mono text-[11px] text-[var(--ink-3)]">
                    {Math.round(crew.data_coverage * 100)}%
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
