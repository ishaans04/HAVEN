"use client";

import { CircleCheck, CircleSlash, Users } from "lucide-react";
import type { CrewReadiness, Situation } from "@/lib/types";
import { Panel, Tag } from "./ui";

const BLOCK_LABEL: Record<string, string> = {
  no_qualified_alternate: "No other crew member holds the qualification",
  alternate_below_alertness_floor: "Qualified alternates are below the alertness floor",
  alternate_committed_elsewhere: "Alternates committed to concurrent safety-critical work",
};

/**
 * Zone 5 — Schedule-Impact Check.
 *
 * Confirms a proposed change does not create a new coverage gap. This screen
 * can veto a well-formed recommendation, so it is shown as its own zone rather
 * than as a footnote on the recommendation.
 */
export function ScheduleImpactPanel({
  situation,
  readiness,
}: {
  situation: Situation | null;
  readiness: CrewReadiness[];
}) {
  const impact = situation?.recommendation?.schedule_impact ?? null;

  return (
    <Panel
      zone="Zone 5"
      title="Schedule-Impact Check"
      hint="Does the proposed change leave every safety-critical role staffed by someone qualified and rested?"
      right={
        impact ? (
          impact.roster_ok ? (
            <Tag tone="good">roster ok</Tag>
          ) : (
            <Tag tone="bad">blocked</Tag>
          )
        ) : null
      }
    >
      <div className="p-4">
        {!situation ? (
          <p className="text-[12px] text-[var(--hv-muted)]">No change proposed.</p>
        ) : !impact ? (
          <p className="text-[12px] text-[var(--hv-muted)]">
            No staffing change was proposed — the flow reached a refusal, so there is nothing to
            screen.
          </p>
        ) : (
          <>
            <div className="flex items-start gap-2">
              {impact.roster_ok ? (
                <CircleCheck size={16} className="mt-0.5 shrink-0 text-[color:var(--hv-nominal)]" />
              ) : (
                <CircleSlash size={16} className="mt-0.5 shrink-0 text-[color:var(--hv-degraded)]" />
              )}
              <p className="text-[12px] leading-relaxed">{impact.note}</p>
            </div>

            {impact.blocked_reason ? (
              <div className="mono mt-2 rounded border border-[color:var(--hv-degraded)]/40 bg-[color:var(--hv-degraded)]/[0.06] px-2.5 py-1.5 text-[10px] text-[color:var(--hv-degraded)]">
                {BLOCK_LABEL[impact.blocked_reason] ?? impact.blocked_reason}
              </div>
            ) : null}

            {impact.alternate ? (
              <div className="mt-3 flex items-center gap-2 rounded border border-[color:var(--hv-nominal)]/40 bg-[color:var(--hv-nominal)]/[0.06] px-2.5 py-2">
                <Users size={14} className="text-[color:var(--hv-nominal)]" />
                <span className="text-[12px]">
                  Proposed cover: <strong>{impact.alternate_name}</strong>
                </span>
                <span className="mono ml-auto text-[10px] text-[var(--hv-muted)]">
                  {impact.alternate}
                </span>
              </div>
            ) : null}

            <div className="hv-zone-label mb-2 mt-4">Safety-critical roles after the change</div>
            <ul className="space-y-1">
              {readiness
                .filter((c) => impact.checked_roles.includes(c.role))
                .map((c) => (
                  <li
                    key={c.crew_member}
                    className="flex items-center gap-2 rounded border border-[var(--hv-line)] bg-[var(--hv-panel-raised)] px-2.5 py-1.5"
                  >
                    <span className="text-[11px]">{c.name}</span>
                    <span className="mono text-[10px] text-[var(--hv-dim)]">
                      {c.role.replace(/_/g, " ")}
                    </span>
                    <span className="mono ml-auto text-[10px] text-[var(--hv-muted)]">
                      alert {c.alertness_score.toFixed(2)}
                    </span>
                    <Tag
                      tone={
                        c.status === "nominal" ? "good" : c.status === "watch" ? "warn" : "bad"
                      }
                    >
                      {c.status}
                    </Tag>
                  </li>
                ))}
            </ul>
          </>
        )}
      </div>
    </Panel>
  );
}
