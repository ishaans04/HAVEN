"use client";

import { useState } from "react";
import clsx from "clsx";
import { ChevronDown, Link2, Lock, Radio, TriangleAlert } from "lucide-react";
import type { AuditRecord, TierStatus } from "@/lib/types";
import { Tag } from "./ui";

/**
 * Zone 6 — Audit Bar.
 *
 * Live tier status plus the logged decision path. The hash chain is shown
 * because "traceable" has to mean something checkable: each entry is bound to
 * the one before it, so an altered step stops verifying.
 */
export function AuditBar({
  tierStatus,
  audit,
  evaluationId,
}: {
  tierStatus: TierStatus;
  audit: AuditRecord | null;
  evaluationId: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="hv-panel">
      {tierStatus.degraded ? (
        <div className="flex items-center gap-2 rounded-t-[10px] border-b border-[color:var(--hv-watch)]/40 bg-[color:var(--hv-watch)]/[0.1] px-4 py-2">
          <TriangleAlert size={14} className="shrink-0 text-[color:var(--hv-watch)]" />
          <span className="text-[11px] text-[color:var(--hv-watch)]">
            <strong>Degraded mode.</strong> {tierStatus.degraded_reason} Deterministic scoring is
            unaffected; procedure interpretation is unavailable and Situations are being escalated.
          </span>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5">
        <span className="flex items-center gap-1.5">
          <Radio
            size={13}
            className={clsx(
              "hv-pulse",
              tierStatus.degraded
                ? "text-[color:var(--hv-watch)]"
                : "text-[color:var(--hv-nominal)]",
            )}
          />
          <span className="hv-zone-label">Zone 6 · Audit</span>
        </span>

        <TierPill label="Deterministic" value={tierStatus.deterministic} tone="good" />
        <TierPill label="Retrieval" value={tierStatus.retrieval} tone="info" />
        <TierPill label="Reasoning" value={tierStatus.reasoning} tone="violet" />
        <TierPill label="Orchestration" value={tierStatus.orchestration} tone="warn" />

        <span className="mono ml-auto text-[10px] text-[var(--hv-dim)]">{evaluationId}</span>

        {audit ? (
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1.5 rounded border border-[var(--hv-line-bright)] px-2 py-1 text-[10px] text-[var(--hv-muted)] transition-colors hover:text-[var(--hv-text)]"
          >
            <Link2 size={11} />
            {audit.audit_ref}
            <ChevronDown
              size={11}
              className={clsx("transition-transform", open && "rotate-180")}
            />
          </button>
        ) : null}
      </div>

      {open && audit ? (
        <div className="border-t border-[var(--hv-line)] px-4 py-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Lock size={12} className="text-[color:var(--hv-nominal)]" />
            <span className="text-[11px]">
              Hash chain{" "}
              <strong
                className={
                  audit.chain_valid
                    ? "text-[color:var(--hv-nominal)]"
                    : "text-[color:var(--hv-degraded)]"
                }
              >
                {audit.chain_valid ? "verified" : "BROKEN"}
              </strong>{" "}
              across {audit.steps.length} steps
            </span>
            <Tag tone="neutral">{audit.provider}</Tag>
            <Tag tone="neutral">{audit.model_id}</Tag>
          </div>

          <div className="max-h-64 overflow-auto rounded border border-[var(--hv-line)]">
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-[var(--hv-panel-raised)]">
                <tr className="hv-zone-label">
                  <th className="px-2 py-1.5 font-normal">#</th>
                  <th className="px-2 py-1.5 font-normal">Step</th>
                  <th className="px-2 py-1.5 font-normal">Tier</th>
                  <th className="px-2 py-1.5 font-normal">Detail</th>
                  <th className="px-2 py-1.5 font-normal">Entry hash</th>
                </tr>
              </thead>
              <tbody>
                {audit.steps.map((step) => (
                  <tr key={step.seq} className="border-t border-[var(--hv-line)] align-top">
                    <td className="mono px-2 py-1.5 text-[10px] text-[var(--hv-dim)]">
                      {step.seq}
                    </td>
                    <td className="mono px-2 py-1.5 text-[10px] font-semibold">{step.step}</td>
                    <td className="mono px-2 py-1.5 text-[10px] text-[var(--hv-muted)]">
                      {step.tier}
                    </td>
                    <td className="px-2 py-1.5 text-[10px] leading-snug text-[var(--hv-muted)]">
                      {step.detail}
                    </td>
                    <td className="mono px-2 py-1.5 text-[10px] text-[var(--hv-dim)]">
                      {step.entry_hash.slice(0, 12)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TierPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "good" | "info" | "violet" | "warn";
}) {
  const colors = {
    good: "var(--hv-nominal)",
    info: "var(--hv-accent)",
    violet: "var(--hv-violet)",
    warn: "var(--hv-watch)",
  } as const;
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: colors[tone] }} />
      <span className="hv-zone-label">{label}</span>
      <span className="mono text-[10px] text-[var(--hv-muted)]">{value}</span>
    </span>
  );
}
