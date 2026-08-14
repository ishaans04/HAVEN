"use client";

import clsx from "clsx";
import type { CrewReadiness } from "@/lib/types";
import { Meter, Panel, StatusDot, Tag, utcTime } from "./ui";

/**
 * Zone 1 — Readiness Overview.
 *
 * Per-crew alertness and workload against that person's own baseline, so an
 * ordinary individual difference is not mistaken for a warning sign.
 */
export function ReadinessOverview({
  readiness,
  selectedCrew,
  onSelect,
}: {
  readiness: CrewReadiness[];
  selectedCrew: string | null;
  onSelect: (crewId: string) => void;
}) {
  return (
    <Panel
      zone="Zone 1"
      title="Readiness Overview"
      hint="Predicted alertness and workload against each operator's personal baseline."
    >
      <ul className="divide-y divide-[var(--hv-line)]">
        {readiness.map((crew) => {
          const selected = crew.crew_member === selectedCrew;
          const deltaTone =
            crew.delta_vs_baseline <= -0.06
              ? "var(--hv-degraded)"
              : crew.delta_vs_baseline >= 0.02
                ? "var(--hv-nominal)"
                : "var(--hv-muted)";
          return (
            <li key={crew.crew_member}>
              <button
                onClick={() => onSelect(crew.crew_member)}
                className={clsx(
                  "w-full px-4 py-3 text-left transition-colors",
                  selected ? "bg-[var(--hv-panel-raised)]" : "hover:bg-[var(--hv-panel-raised)]/60",
                )}
              >
                <div className="flex items-center gap-2">
                  <StatusDot status={crew.status} pulse={crew.status === "degraded"} />
                  <span className="text-[13px] font-medium">{crew.name}</span>
                  <span className="mono text-[10px] text-[var(--hv-dim)]">
                    {crew.crew_member} · {crew.role.replace(/_/g, " ")}
                  </span>
                  <span className="ml-auto flex items-center gap-1.5">
                    {crew.confidence === "insufficient" || crew.confidence === "low" ? (
                      <Tag tone="warn">record {Math.round(crew.data_coverage * 100)}%</Tag>
                    ) : null}
                    {crew.trend === "declining" ? <Tag tone="bad">declining</Tag> : null}
                  </span>
                </div>

                <div className="mt-2 grid grid-cols-[1fr_auto] items-center gap-3">
                  <div>
                    <div className="flex items-baseline justify-between text-[10px] text-[var(--hv-dim)]">
                      <span>alertness</span>
                      <span className="mono">
                        <span className="text-[13px] text-[var(--hv-text)]">
                          {crew.alertness_score.toFixed(2)}
                        </span>
                        <span className="ml-1">base {crew.baseline_alertness.toFixed(2)}</span>
                      </span>
                    </div>
                    <div className="mt-1">
                      <Meter
                        value={crew.alertness_score}
                        threshold={crew.baseline_alertness}
                        color={
                          crew.status === "degraded"
                            ? "var(--hv-degraded)"
                            : crew.status === "watch"
                              ? "var(--hv-watch)"
                              : "var(--hv-nominal)"
                        }
                      />
                    </div>
                  </div>
                  <div className="mono text-right text-[11px]" style={{ color: deltaTone }}>
                    {crew.delta_vs_baseline >= 0 ? "+" : ""}
                    {crew.delta_vs_baseline.toFixed(2)}
                  </div>
                </div>

                <div className="mono mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[var(--hv-dim)]">
                  <span>TLX {crew.workload_score.toFixed(0)}</span>
                  <span>debt {crew.sleep_debt_h.toFixed(1)}h</span>
                  <span>awake {crew.hours_awake.toFixed(1)}h</span>
                  <span>
                    window low {crew.window_min_alertness.toFixed(2)} @{" "}
                    {utcTime(crew.window_min_at)}
                  </span>
                  <span className="text-[var(--hv-dim)]">
                    {crew.asleep_at_window_start ? "asleep at 00:00Z · read " : "read "}
                    {utcTime(crew.reference_at)}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
