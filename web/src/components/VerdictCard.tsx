"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { ArrowRight, Check, CircleSlash, ShieldAlert, UserCheck, X } from "lucide-react";
import type { CrewReadiness, Situation } from "@/lib/types";
import { recordDecision } from "@/lib/api";
import { EscalationTarget, RefusalBlock } from "./RefusalBlock";
import { RosterSeats } from "./RosterSeats";
import { Vitals } from "./Vitals";
import { Chip, Disclosure, GlassCard, Label, Meter, TONE_VAR, toneOf, utcTime } from "./ui";

const CONFIDENCE_TONE: Record<string, "ok" | "warn" | "bad"> = {
  high: "ok",
  moderate: "warn",
  low: "warn",
  insufficient: "bad",
};

const BLOCK_LABEL: Record<string, string> = {
  no_qualified_alternate: "No other crew member holds the qualification",
  alternate_below_alertness_floor: "Qualified alternates are below the alertness floor",
  alternate_committed_elsewhere: "Alternates are committed to concurrent safety-critical work",
};

const humanise = (value: string) => value.replace(/_/g, " ");

/**
 * The answer.
 *
 * This card exists because v1 answered in the wrong order. It led with the
 * evidence — four readouts, a paragraph of grounded rationale, a citation, a
 * cost line, a projection — and left the reader to assemble the conclusion. A
 * specialist does that assembly for free. Everyone else reads a wall.
 *
 * So the order is inverted: what to do, then why in one plain sentence, then
 * the numbers that back it, then everything else behind a disclosure. Nothing
 * was deleted to achieve that. The rationale, the cost, the projection, the
 * roster check and the clause-level refusal detail are all still on this card;
 * they are just no longer the first thing competing for the first read.
 *
 * A refusal is styled as a different kind of answer rather than as a failed
 * recommendation, because that is what it is.
 */
export function VerdictCard({
  situation,
  readiness,
}: {
  situation: Situation | null;
  readiness: CrewReadiness[];
}) {
  const [decision, setDecision] = useState<"approved" | "overridden" | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDecision(null);
    setReason("");
  }, [situation?.situation_id]);

  if (!situation) {
    return (
      <GlassCard className="flex min-h-[280px] flex-col items-center justify-center p-8 text-center">
        <div className="glass-3 mb-4 rounded-full p-3">
          <Check size={20} className="text-[var(--ok)]" />
        </div>
        <h2 className="display text-[26px]">Nothing needs a decision</h2>
        <p className="mt-3 max-w-sm text-[13px] leading-relaxed text-[var(--ink-2)]">
          Every task in this window cleared the deterministic trigger. A quiet console is a
          valid state, not a broken one. The tier strip below shows the system is live.
        </p>
      </GlassCard>
    );
  }

  const isRefusal = situation.outcome === "refusal";
  const rec = situation.recommendation;
  const ref = situation.refusal;
  const impact = rec?.schedule_impact ?? null;
  const projection = rec?.projection ?? null;
  const riskTone = toneOf(situation.risk_level);

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
    <GlassCard live={!isRefusal} refuse={isRefusal} className="overflow-hidden">
      {/* Header — who and when, and how bad. */}
      <div className="flex flex-wrap items-start gap-3 px-5 pt-5">
        <div className="min-w-0 flex-1">
          <Label>{isRefusal ? "HAVEN is refusing" : "HAVEN recommends"}</Label>
          <p className="mono mt-2 text-[12px] text-[var(--ink-3)]">
            {situation.crew_member_name} · {situation.task} · {utcTime(situation.task_scheduled)}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Chip tone={riskTone} solid>
            {situation.risk_level}
          </Chip>
          <Chip tone={CONFIDENCE_TONE[situation.confidence] ?? "neutral"}>
            {situation.confidence} confidence
          </Chip>
        </div>
      </div>

      {/* The headline and the one-sentence reason. */}
      <div className="px-5 pt-4">
        <h2 className="display text-[26px] sm:text-[34px] xl:text-[38px]">
          {isRefusal ? (
            <span className="flex items-start gap-3">
              <ShieldAlert size={26} className="mt-2 shrink-0 text-[var(--bad)]" />
              <span>{ref?.reason_label ?? "No governing procedure"}</span>
            </span>
          ) : (
            rec?.action_label
          )}
        </h2>

        <p className="mt-4 max-w-2xl text-[16px] leading-relaxed text-[var(--ink-2)]">
          {isRefusal ? (
            ref?.explanation
          ) : (
            <>
              <span className="text-[var(--ink)]">{situation.crew_member_name}</span> is predicted at{" "}
              <span className="readout text-[16px]" style={{ color: TONE_VAR[riskTone] }}>
                {situation.alertness_score.toFixed(2)}
              </span>{" "}
              alertness
              {projection ? (
                <>
                  {" "}
                  against a line of{" "}
                  <span className="readout text-[16px]">{projection.threshold.toFixed(2)}</span> for
                  this job
                </>
              ) : null}
              , with {humanise(situation.task_label)} due at {utcTime(situation.task_scheduled)} at{" "}
              {situation.task_criticality} criticality
              {situation.circadian_flag ? ", inside their body-clock low" : ""}.
            </>
          )}
        </p>

        {isRefusal && ref ? <RefusalBlock refusal={ref} situation={situation} /> : null}

        {rec ? (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Chip tone="info">
              {rec.citation.doc} §{rec.citation.section}
            </Chip>
            <span className="text-[13px] text-[var(--ink-3)]">
              <span className="uppercase tracking-[0.11em] text-[11px] font-medium">Cost</span>
              {" · "}
              {rec.resource_cost}
            </span>
          </div>
        ) : null}
      </div>

      {/* The deterministic evidence, as one reading rather than four boxes. */}
      <div className="mt-6 px-5">
        <Vitals situation={situation} />
      </div>

      {/* What the action is predicted to buy. */}
      {projection ? (
        <div className="mt-3 px-5">
          <div className="glass-2 p-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <Label className="!text-[11px]">Predicted effect</Label>
              <div className="flex items-baseline gap-2">
                <span className="readout text-[19px] text-[var(--ink-3)]">
                  {projection.before.toFixed(2)}
                </span>
                <ArrowRight size={14} className="text-[var(--ink-3)]" />
                <span
                  className="readout text-[26px]"
                  style={{
                    color: projection.clears_threshold
                      ? "var(--ok)"
                      : projection.delta > 0
                        ? "var(--warn)"
                        : "var(--bad)",
                  }}
                >
                  {projection.after.toFixed(2)}
                </span>
                <span className="text-[12px] text-[var(--ink-3)]">
                  {projection.delta >= 0 ? "+" : ""}
                  {projection.delta.toFixed(3)}
                </span>
              </div>
              <Chip
                tone={projection.clears_threshold ? "ok" : "warn"}
                className="ml-auto"
              >
                {projection.clears_threshold ? "clears the line" : "still below the line"}
              </Chip>
            </div>
            <div className="mt-3">
              <Meter
                value={projection.after}
                threshold={projection.threshold}
                height={5}
                color={projection.clears_threshold ? "var(--ok)" : "var(--warn)"}
              />
            </div>
            <p className="mt-2 text-[12px] leading-snug text-[var(--ink-3)]">
              {projection.subject_name ? `${projection.subject_name}. ` : ""}
              {projection.basis} A projection under the Three-Process Model, not a
              measurement. Nothing here observes the crew afterwards.
            </p>
          </div>
        </div>
      ) : null}

      {/* Does the fix break the crew? Six seats say it faster than the note did. */}
      {impact ? (
        <div className="mt-3 px-5">
          <div className="glass-2 p-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
              {impact.roster_ok ? (
                <UserCheck size={15} className="shrink-0 text-[var(--ok)]" />
              ) : (
                <CircleSlash size={15} className="shrink-0 text-[var(--bad)]" />
              )}
              <Label className="!text-[11px]">
                {impact.roster_ok ? "Roster holds" : "Roster blocked"}
              </Label>
              {impact.blocked_reason ? (
                <Chip tone="bad">
                  {BLOCK_LABEL[impact.blocked_reason] ?? impact.blocked_reason}
                </Chip>
              ) : null}
              <span className="mono ml-auto text-[11px] text-[var(--ink-3)]">
                {impact.checked_roles.length} role
                {impact.checked_roles.length === 1 ? "" : "s"} screened
              </span>
            </div>
            <div className="mt-4">
              <RosterSeats
                readiness={readiness}
                impact={impact}
                subject={situation.crew_member}
              />
            </div>
          </div>
        </div>
      ) : null}

      {/* Everything v1 showed by default, kept and demoted. */}
      <div className="mt-3 space-y-2 px-5">
        {rec ? (
          <Disclosure
            summary="The full rationale, as cited"
            hint={`Grounded in ${rec.citation.doc} section ${rec.citation.section}`}
          >
            <div className="glass-2 p-4">
              <p className="text-[13px] leading-relaxed text-[var(--ink-2)]">{rec.rationale}</p>
            </div>
          </Disclosure>
        ) : null}


      </div>

      {/* Stage 7. HAVEN never actions anything itself. */}
      <div
        className="mt-5 px-5 py-4"
        style={{
          background: "rgba(255,255,255,0.03)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.07)",
        }}
      >
        {decision ? (
          <div className="flex items-start gap-2 text-[13px] text-[var(--ink-2)]">
            {decision === "approved" ? (
              <Check size={16} className="mt-1 shrink-0 text-[var(--ok)]" />
            ) : (
              <X size={16} className="mt-1 shrink-0 text-[var(--warn)]" />
            )}
            <span>
              Recorded as <strong className="font-medium text-[var(--ink)]">{decision}</strong>{" "}
              against <span className="mono text-[12px]">{situation.audit_ref}</span>. HAVEN has
              taken no action — the operator owns the change.
            </span>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <p className="text-[13px] text-[var(--ink-3)]">
                HAVEN does not execute, defer, or reassign. Record the operator decision.
              </p>
              {/* On a refusal the escalation target is the action, so it belongs
                  next to the button rather than in a chip further up. */}
              {isRefusal && ref ? <EscalationTarget refusal={ref} /> : null}
            </div>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason (logged with the decision)"
                aria-label="Reason, logged with the decision"
                className="min-w-0 flex-1 rounded-full bg-white/[0.05] px-4 py-2.5 text-[13px] text-[var(--ink)] outline-none transition-shadow placeholder:text-[var(--ink-3)]"
                style={{ boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.12)" }}
              />
              <div className="flex gap-2">
                <DecisionButton
                  tone="ok"
                  disabled={saving}
                  onClick={() => submit("approved")}
                  label={isRefusal ? "Acknowledge & escalate" : "Approve"}
                />
                <DecisionButton
                  tone="warn"
                  disabled={saving}
                  onClick={() => submit("overridden")}
                  label="Override"
                />
              </div>
            </div>
          </>
        )}
      </div>
    </GlassCard>
  );
}

function DecisionButton({
  tone,
  label,
  disabled,
  onClick,
}: {
  tone: "ok" | "warn";
  label: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  const color = TONE_VAR[tone];
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={clsx(
        "glass-interactive shrink-0 rounded-full px-5 py-2.5 text-[13px] font-medium disabled:opacity-50",
      )}
      style={{
        color,
        background: `color-mix(in oklab, ${color} 16%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${color} 42%, transparent)`,
      }}
    >
      {label}
    </button>
  );
}
