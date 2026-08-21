"use client";

import { TrendingDown } from "lucide-react";
import type { CrewReadiness } from "@/lib/types";
import { Chip, Ring, toneOf } from "./ui";

/**
 * Zone 1 — Readiness Overview, reduced to what a scan needs.
 *
 * v1 put six numbers on every one of six crew cards: alertness, baseline,
 * delta, TLX, sleep debt, hours awake, window minimum, and the time the record
 * was read. Thirty-odd figures, all at 10px, none of them the question being
 * asked at this altitude — which is only ever "who here is running low?"
 *
 * So the rail carries one dial per person and a word for the state. The rest of
 * it is intact and one click away, under "the numbers", where somebody who
 * wants the trailing sleep debt to one decimal place can have it.
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
    <div className="fade-x no-bar flex gap-2.5 overflow-x-auto px-1 pb-1">
      {readiness.map((crew) => {
        const active = crew.crew_member === selected;
        const tone = toneOf(crew.status);
        return (
          <button
            key={crew.crew_member}
            onClick={() => onSelect(crew.crew_member)}
            aria-pressed={active}
            className="selectable flex w-[186px] shrink-0 items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2.5 text-left"
          >
            <Ring value={crew.alertness_score} tone={tone} size={42}>
              <span className="readout text-[12px] text-[var(--ink)]">
                {crew.alertness_score.toFixed(2).slice(1)}
              </span>
            </Ring>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13.5px] font-medium text-[var(--ink)]">
                {crew.name}
              </span>
              <span className="mt-0.5 block truncate text-[11.5px] capitalize text-[var(--ink-3)]">
                {crew.role.replace(/_/g, " ")}
              </span>
              {crew.trend === "declining" ? (
                <span className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-[var(--bad)]">
                  <TrendingDown size={11} />
                  declining
                </span>
              ) : crew.status !== "nominal" ? (
                <span className="mt-1.5 block text-[11px] capitalize text-[var(--warn)]">
                  {crew.status}
                </span>
              ) : null}
            </span>
          </button>
        );
      })}
    </div>
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
      <table className="w-full border-collapse text-left text-[12.5px]">
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
