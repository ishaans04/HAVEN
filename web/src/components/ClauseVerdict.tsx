"use client";

import clsx from "clsx";
import { Check, X } from "lucide-react";
import type { ClauseDetail } from "@/lib/types";

/**
 * The deterministic checker's verdict, clause by clause.
 *
 * This is the half of propose/dispose that has had nowhere to appear. The model
 * proposes a passage and says why in prose; the checker evaluates that passage's
 * compiled preconditions and returns a verdict per clause. Showing only the
 * model's reasoning would leave an operator taking the citation on trust — which
 * is precisely the posture this architecture was built to replace.
 *
 * Satisfied clauses are rendered as well as failed ones, deliberately. A single
 * red line invites the reading "fix that one thing and it would apply"; the full
 * test shows what was actually asked. It is also the difference between a
 * passage that failed on one clause of five and one that failed on four.
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
      <p className="text-[10px] italic text-[var(--hv-dim)]">
        This passage declares no preconditions.
      </p>
    );
  }

  return (
    <ul className={clsx("space-y-1", compact && "space-y-0.5")}>
      {clauses.map((clause) => (
        <li key={clause.clause} className="flex items-start gap-1.5">
          {clause.satisfied ? (
            <Check size={11} className="mt-[3px] shrink-0 text-[color:var(--hv-nominal)]" />
          ) : (
            <X size={11} className="mt-[3px] shrink-0 text-[color:var(--hv-degraded)]" />
          )}
          <span className="min-w-0 flex-1">
            <span className="mono text-[10px] text-[var(--hv-muted)]">{clause.clause}</span>
            {!compact ? (
              <span className="ml-1.5 text-[10px] text-[var(--hv-dim)]">
                wants <span className="mono text-[var(--hv-muted)]">{clause.expected}</span>
                {" · got "}
                <span
                  className={clsx(
                    "mono",
                    clause.satisfied
                      ? "text-[var(--hv-muted)]"
                      : "text-[color:var(--hv-degraded)]",
                  )}
                >
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
      className="mono shrink-0 text-[10px]"
      style={{ color: all ? "var(--hv-nominal)" : "var(--hv-degraded)" }}
    >
      {met}/{clauses.length}
    </span>
  );
}
