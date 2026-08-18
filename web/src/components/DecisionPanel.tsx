"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, Check, ShieldAlert, X } from "lucide-react";
import type { Situation } from "@/lib/types";
import { recordDecision } from "@/lib/api";
import { ProjectionPanel } from "./ProjectionPanel";
import { Meter, Panel, Stat, Tag, utcTime } from "./ui";

const CONFIDENCE_TONE: Record<string, "good" | "warn" | "bad"> = {
  high: "good",
  moderate: "warn",
  low: "warn",
  insufficient: "bad",
};

/**
 * Zone 4 — Recommendation / Refusal.
 *
 * The decision object. A refusal is styled deliberately differently from a
 * recommendation: it is a correct output, not an error state, and must not be
 * mistaken for one at a glance.
 */
export function DecisionPanel({ situation }: { situation: Situation | null }) {
  const [decision, setDecision] = useState<"approved" | "overridden" | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDecision(null);
    setReason("");
  }, [situation?.situation_id]);

  if (!situation) {
    return (
      <Panel zone="Zone 4" title="Recommendation / Refusal">
        <div className="flex h-full items-center justify-center p-6 text-center text-[12px] text-[var(--hv-muted)]">
          No Situation raised. A quiet console is a valid state — the audit bar below shows the
          system is live.
        </div>
      </Panel>
    );
  }

  const isRefusal = situation.outcome === "refusal";
  const rec = situation.recommendation;
  const ref = situation.refusal;

  async function submit(choice: "approved" | "overridden") {
    if (!situation) return;
    setSaving(true);
    try {
      await recordDecision({
        situation_id: situation.situation_id,
        audit_ref: situation.audit_ref,
        decision: choice,
        reason,
      });
      setDecision(choice);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel
      zone="Zone 4"
      title={isRefusal ? "Refusal — escalation required" : "Recommendation"}
      hint={`${situation.situation_id} · ${situation.crew_member_name} · ${situation.task} at ${utcTime(situation.task_scheduled)}`}
      right={
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Tag tone={situation.risk_level === "critical" ? "bad" : "warn"}>
            {situation.risk_level}
          </Tag>
          <Tag tone={CONFIDENCE_TONE[situation.confidence]}>
            confidence {situation.confidence}
          </Tag>
        </div>
      }
      className={clsx(
        isRefusal && "border-[color:var(--hv-degraded)] shadow-[0_0_0_1px_rgba(255,107,94,0.25)]",
      )}
    >
      <div className="space-y-4 p-4">
        {/* Deterministic evidence, shown before the prose so the numbers anchor it. */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label="Alertness"
            value={situation.alertness_score.toFixed(2)}
            sub="Three-Process Model"
            tone={
              situation.alertness_score < 0.6
                ? "var(--hv-degraded)"
                : situation.alertness_score < 0.7
                  ? "var(--hv-watch)"
                  : "var(--hv-nominal)"
            }
          />
          <Stat
            label="Workload"
            value={situation.workload_score.toFixed(0)}
            sub={`NASA-TLX · ${situation.evidence.workload_band.replace("_", " ")}`}
          />
          <Stat
            label="Awake"
            value={`${situation.evidence.hours_awake.toFixed(1)}h`}
            sub={`debt ${situation.evidence.sleep_debt_h.toFixed(1)}h`}
          />
          <Stat
            label="Circadian"
            value={situation.circadian_flag ? "TROUGH" : "clear"}
            sub={`KSS ${situation.evidence.kss.toFixed(1)}`}
            tone={situation.circadian_flag ? "var(--hv-degraded)" : undefined}
          />
        </div>

        {isRefusal && ref ? (
          <div className="rounded border border-[color:var(--hv-degraded)]/50 bg-[color:var(--hv-degraded)]/[0.07] p-3">
            <div className="flex items-center gap-2">
              <ShieldAlert size={15} className="text-[color:var(--hv-degraded)]" />
              <span className="text-[13px] font-semibold text-[color:var(--hv-degraded)]">
                {ref.reason_label}
              </span>
              <Tag tone="bad">escalate to {ref.escalate_to.replace(/_/g, " ")}</Tag>
            </div>
            <p className="mt-2 text-[12px] leading-relaxed text-[var(--hv-text)]">
              {ref.explanation}
            </p>

            {ref.searched.length > 0 ? (
              <div className="mt-3">
                <div className="hv-zone-label">Searched</div>
                <div className="mono mt-1 flex flex-wrap gap-1.5">
                  {ref.searched.map((doc) => (
                    <span
                      key={doc}
                      className="rounded border border-[var(--hv-line-bright)] px-1.5 py-0.5 text-[10px] text-[var(--hv-muted)]"
                    >
                      {doc}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Why the refusal happened: the compiled clauses the deterministic
                checker found unsatisfied in the passage the model proposed. This
                is the reason, and it is stated in the operator's terms. */}
            {ref.failed_clauses.length > 0 ? (
              <div className="mt-3">
                <div className="hv-zone-label">
                  Checker rejected {ref.model_selected} — unsatisfied preconditions
                </div>
                <ul className="mt-1 space-y-1">
                  {ref.failed_clauses.map((clause) => (
                    <li key={clause.clause} className="text-[11px] leading-snug">
                      <span className="mono text-[10px] text-[var(--hv-dim)]">{clause.clause}</span>{" "}
                      <span className="text-[var(--hv-muted)]">
                        expected {clause.expected}, actual {clause.actual}
                      </span>
                      <div className="text-[color:var(--hv-degraded)]">{clause.explanation}</div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* Retrieval similarity, shown because it explains what was *found*.
                It decides nothing: admissibility is settled clause by clause
                above, and the gate is a display floor. */}
            {ref.best_candidate ? (
              <div className="mt-3">
                <div className="flex items-baseline justify-between">
                  <span className="hv-zone-label">
                    Closest candidate — {ref.best_candidate.doc} §{ref.best_candidate.section}
                  </span>
                  <span className="mono text-[10px] text-[var(--hv-muted)]">
                    retrieval similarity {ref.best_candidate.relevance.toFixed(3)}
                  </span>
                </div>
                <div className="mt-1">
                  <Meter
                    value={ref.best_candidate.relevance}
                    threshold={ref.gate}
                    color="var(--hv-degraded)"
                    height={5}
                  />
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {rec ? (
          <div className="rounded border border-[var(--hv-line-bright)] bg-[var(--hv-panel-raised)] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[14px] font-semibold">{rec.action_label}</span>
              <Tag tone="info">
                {rec.citation.doc} §{rec.citation.section}
              </Tag>
              {!rec.schedule_impact.roster_ok ? (
                <Tag tone="warn">downgraded by screen</Tag>
              ) : null}
            </div>
            <p className="mt-2 text-[12px] leading-relaxed text-[var(--hv-text)]">
              {rec.rationale}
            </p>
            <div className="mono mt-2 text-[10px] text-[var(--hv-dim)]">
              Cost — {rec.resource_cost}
            </div>
            {/* What the cost buys. Rendered next to it deliberately: a cost
                without a benefit is half an argument. */}
            {rec.projection ? (
              <div className="mt-3">
                <ProjectionPanel projection={rec.projection} />
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Stage 7: human approval. HAVEN never actions anything itself. */}
        <div className="border-t border-[var(--hv-line)] pt-3">
          {decision ? (
            <div className="flex items-center gap-2 text-[12px]">
              {decision === "approved" ? (
                <Check size={15} className="text-[color:var(--hv-nominal)]" />
              ) : (
                <X size={15} className="text-[color:var(--hv-watch)]" />
              )}
              <span>
                Recorded as <strong>{decision}</strong> against {situation.audit_ref}. HAVEN has
                taken no action; the operator owns the change.
              </span>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <AlertTriangle size={13} className="text-[var(--hv-dim)]" />
                <span className="text-[11px] text-[var(--hv-muted)]">
                  HAVEN does not execute, defer, or reassign. Record the operator decision.
                </span>
              </div>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <input
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Reason (logged with the decision)"
                  className="mono min-w-0 flex-1 rounded border border-[var(--hv-line-bright)] bg-[var(--hv-bg)] px-2.5 py-1.5 text-[11px] outline-none placeholder:text-[var(--hv-dim)] focus:border-[color:var(--hv-accent)]"
                />
                <div className="flex gap-2">
                  <button
                    disabled={saving}
                    onClick={() => submit("approved")}
                    className="rounded border border-[color:var(--hv-nominal)] px-3 py-1.5 text-[11px] font-medium text-[color:var(--hv-nominal)] transition-colors hover:bg-[color:var(--hv-nominal)]/10 disabled:opacity-50"
                  >
                    {isRefusal ? "Acknowledge & escalate" : "Approve"}
                  </button>
                  <button
                    disabled={saving}
                    onClick={() => submit("overridden")}
                    className="rounded border border-[color:var(--hv-watch)] px-3 py-1.5 text-[11px] font-medium text-[color:var(--hv-watch)] transition-colors hover:bg-[color:var(--hv-watch)]/10 disabled:opacity-50"
                  >
                    Override
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}
