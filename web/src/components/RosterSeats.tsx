"use client";

import clsx from "clsx";
import type { CrewReadiness, ScheduleImpact } from "@/lib/types";
import { Ring, toneOf } from "./ui";

const DESIGNATOR: Record<string, string> = {
  commander: "CDR",
  flight_engineer: "FE",
  mission_specialist: "MS",
};

/**
 * Does the fix break the crew?
 *
 * That is a spatial question and it was being answered in a sentence plus a
 * four-row list. Six seats answer it at a glance: who steps back, who covers,
 * who is merely staffed, and — the part the prose never mentioned — which roles
 * the screen actually examined. Mission specialists sit dimmed here because the
 * check did not apply to them, which is information the paragraph withheld by
 * simply not listing them.
 */
export function RosterSeats({
  readiness,
  impact,
  subject,
}: {
  readiness: CrewReadiness[];
  impact: ScheduleImpact;
  /** The operator the Situation concerns, who is the one stepping back. */
  subject: string;
}) {
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
      {readiness.map((crew) => {
        const inScope = impact.checked_roles.includes(crew.role);
        const isCover = crew.crew_member === impact.alternate;
        const isSubject = crew.crew_member === subject;

        const state = isSubject
          ? { text: "steps back", colour: "var(--bad)" }
          : isCover
            ? { text: "covers", colour: "var(--ok)" }
            : inScope
              ? { text: "staffed", colour: "var(--ink-3)" }
              : { text: "not in scope", colour: "var(--ink-3)" };

        return (
          <div
            key={crew.crew_member}
            className={clsx(
              "rounded-[var(--radius-sm)] px-2 pb-2.5 pt-3 text-center",
              !inScope && "opacity-45",
              isSubject && "opacity-70",
            )}
            style={{
              background: isCover ? "rgba(92,228,191,0.07)" : "rgba(255,255,255,0.04)",
              boxShadow: isCover
                ? "inset 0 0 0 1px rgba(92,228,191,0.42)"
                : "inset 0 0 0 1px rgba(255,255,255,0.05)",
            }}
          >
            <span className="mx-auto flex justify-center">
              <Ring
                value={crew.alertness_score}
                tone={isSubject ? "bad" : toneOf(crew.status)}
                size={38}
                stroke={3}
              >
                <span className="readout text-[11px] text-[var(--ink)]">
                  {crew.alertness_score.toFixed(2).slice(1)}
                </span>
              </Ring>
            </span>
            <div className="mt-2 truncate text-[11.5px] text-[var(--ink)]">{crew.name}</div>
            <div className="mono mt-0.5 text-[9.5px] uppercase tracking-[0.1em] text-[var(--ink-3)]">
              {DESIGNATOR[crew.role] ?? crew.role.replace(/_/g, " ")}
            </div>
            <div
              className="mono mt-1.5 text-[9px] uppercase tracking-[0.1em]"
              style={{ color: state.colour }}
            >
              {state.text}
            </div>
          </div>
        );
      })}
    </div>
  );
}
