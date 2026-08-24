"use client";

import clsx from "clsx";
import type { CrewReadiness, ScheduleImpact } from "@/lib/types";
import { TONE_VAR, toneOf } from "./ui";

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
    <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(96px,1fr))]">
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
              background: isCover ? "color-mix(in oklab, var(--ok) 7%, transparent)" : "rgba(255,255,255,0.04)",
              boxShadow: isCover
                ? "inset 0 0 0 1px color-mix(in oklab, var(--ok) 42%, transparent)"
                : "inset 0 0 0 1px rgba(255,255,255,0.05)",
            }}
          >
            {/* The figure, plainly. It used to be wrapped in a ring gauge, and
                the ring was doing no work here: this operator's alertness is
                already drawn on a shared scale in the roster above, and the
                question this block answers is not how alert anybody is but
                whether the seats still cover the job. A gauge repeating a
                number from another section, in the section where it is not the
                point, is decoration — so the number stays and the ring goes,
                which leaves the state line below as the loudest thing in the
                seat, where the answer actually is. */}
            <span
              className="readout block text-[17px] leading-none"
              style={{ color: TONE_VAR[isSubject ? "bad" : toneOf(crew.status)] }}
            >
              {crew.alertness_score.toFixed(2).slice(1)}
            </span>
            <div className="mt-2 truncate text-[12px] text-[var(--ink)]">{crew.name}</div>
            <div className="mono mt-1 text-[11px] uppercase tracking-[0.1em] text-[var(--ink-3)]">
              {DESIGNATOR[crew.role] ?? crew.role.replace(/_/g, " ")}
            </div>
            <div
              className="mono mt-2 text-[11px] uppercase tracking-[0.1em]"
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
