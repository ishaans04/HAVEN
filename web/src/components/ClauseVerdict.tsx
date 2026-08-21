"use client";

import clsx from "clsx";
import { Check, X } from "lucide-react";
import type { ClauseDetail } from "@/lib/types";

/**
 * The deterministic checker's verdict, clause by clause.
 *
 * The half of propose/dispose that would otherwise have nowhere to appear. The
 * model proposes a passage and says why in prose; the checker evaluates that
 * passage's compiled preconditions and returns a verdict per clause. Showing
 * only the model's reasoning would leave an operator taking the citation on
 * trust — precisely the posture this architecture was built to replace.
 *
 * Satisfied clauses are rendered as well as failed ones, deliberately. A single
 * red line invites the reading "fix that one thing and it would apply"; the full
 * test shows what was actually asked, and the difference between a passage that
 * failed one clause of five and one that failed four.
 */
export function ClauseVerdict({
  clauses,
  compact = false,
}: {
  clauses: ClauseDetail[];
  compact?: boolean;
}) {
  if (!clauses.length) {
    return (
      <p className="text-[11.5px] italic text-[var(--ink-3)]">
        This passage declares no preconditions.
      </p>
    );
  }

  return (
    <ul className={clsx("space-y-1.5", compact && "space-y-1")}>
      {clauses.map((clause) => (
        <li key={clause.clause} className="flex items-start gap-2">
          {clause.satisfied ? (
            <Check size={13} className="mt-[2px] shrink-0 text-[var(--ok)]" />
          ) : (
            <X size={13} className="mt-[2px] shrink-0 text-[var(--bad)]" />
          )}
          <span className="min-w-0 flex-1 text-[11.5px] leading-snug">
            <span className="mono text-[var(--ink-2)]">{clause.clause}</span>
            {!compact ? (
              <span className="ml-1.5 text-[var(--ink-3)]">
                wants <span className="mono">{clause.expected}</span>
                {" · got "}
                <span className={clsx("mono", !clause.satisfied && "text-[var(--bad)]")}>
                  {clause.actual}
                </span>
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** How many of the checker's conditions a passage met. */
export function ClauseTally({ clauses }: { clauses: ClauseDetail[] }) {
  const met = clauses.filter((c) => c.satisfied).length;
  const all = met === clauses.length && clauses.length > 0;
  return (
    <span
      className="readout shrink-0 text-[12px]"
      style={{ color: all ? "var(--ok)" : "var(--bad)" }}
    >
      {met}/{clauses.length}
    </span>
  );
}
