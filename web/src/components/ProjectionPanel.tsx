"use client";

import clsx from "clsx";
import { ArrowRight, TrendingUp } from "lucide-react";
import type { Projection } from "@/lib/types";
import { Meter, utcTime } from "./ui";

/**
 * What the recommended action is predicted to achieve.
 *
 * A recommendation asks an operator to accept a cost. This says what it buys,
 * which is the same recommendation with its reasoning completed.
 *
 * The wording is careful on purpose. "Predicted", never "achieved": the
 * Three-Process Model says what alertness *would be* under a stated schedule,
 * and nothing here observes the crew afterwards. The basis line is rendered
 * rather than tucked into a tooltip because a projection whose assumptions are
 * hidden is indistinguishable from a measurement, and that is exactly the false
 * confidence this system exists to avoid.
 *
 * It can also disagree with the recommendation it accompanies — an action that
 * does not clear the threshold is shown as not clearing it. That is information
 * an operator should have, not a rendering bug.
 */
export function ProjectionPanel({ projection }: { projection: Projection }) {
  const improves = projection.delta > 0;
  const tone = projection.clears_threshold
    ? "var(--hv-nominal)"
    : improves
      ? "var(--hv-watch)"
      : "var(--hv-degraded)";

  return (
    <div className="rounded border border-[var(--hv-line-bright)] bg-[var(--hv-panel-raised)] p-3">
      <div className="flex items-center gap-2">
        <TrendingUp size={13} style={{ color: tone }} />
        <span className="hv-zone-label">Predicted effect</span>
        <span className="mono ml-auto text-[10px] text-[var(--hv-dim)]">
          at {utcTime(projection.at)}
        </span>
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="mono text-[15px] text-[var(--hv-muted)]">
          {projection.before.toFixed(2)}
        </span>
        <ArrowRight size={12} className="text-[var(--hv-dim)]" />
        <span className="mono text-[18px] font-semibold" style={{ color: tone }}>
          {projection.after.toFixed(2)}
        </span>
        <span className="mono text-[11px]" style={{ color: tone }}>
          {projection.delta >= 0 ? "+" : ""}
          {projection.delta.toFixed(3)}
        </span>
        <span
          className={clsx(
            "mono ml-auto rounded border px-1.5 py-0.5 text-[9px] uppercase tracking-wider",
          )}
          style={{ color: tone, borderColor: tone }}
        >
          {projection.clears_threshold ? "clears threshold" : "still below threshold"}
        </span>
      </div>

      <div className="mt-2">
        <Meter
          value={projection.after}
          threshold={projection.threshold}
          color={tone}
          height={5}
        />
      </div>

      <div className="mt-2 text-[10px] leading-snug text-[var(--hv-dim)]">
        {projection.subject_name ? (
          <span className="text-[var(--hv-muted)]">{projection.subject_name}. </span>
        ) : null}
        {projection.basis}
      </div>

      <div className="mt-1.5 text-[9px] italic leading-snug text-[var(--hv-dim)]">
        A projection under the Three-Process Model, not a measurement. Nothing here observes the
        crew afterwards; confirming the effect is a deferred capability.
      </div>
    </div>
  );
}
