"use client";

import clsx from "clsx";
import { Link2, Lock, Radio, TriangleAlert } from "lucide-react";
import type { AuditRecord, TierStatus } from "@/lib/types";
import { Term } from "./Term";
import { Disclosure, GlassCard, Label } from "./ui";

/**
 * Zone 6 — the audit strip.
 *
 * Which tier is live, which provider answered, and the hash chain. It is shown
 * because "traceable" has to mean something checkable: each entry is bound to
 * the one before it, so an altered step stops verifying. It is also the surface
 * that distinguishes a quiet system from a broken one, which is why it stays
 * visible even when there is nothing to decide.
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
  return (
    <GlassCard className="overflow-hidden">
      {tierStatus.degraded ? (
        <div
          className="flex items-start gap-2 px-5 py-3"
          style={{
            background: "color-mix(in oklab, var(--warn) 9%, transparent)",
            boxShadow: "inset 0 -1px 0 color-mix(in oklab, var(--warn) 24%, transparent)",
          }}
        >
          <TriangleAlert size={15} className="mt-[2px] shrink-0 text-[var(--warn)]" />
          <p className="text-[13px] leading-snug text-[var(--warn)]">
            <strong className="font-medium">Running degraded.</strong> {tierStatus.degraded_reason}{" "}
            The maths is unaffected and every figure is still real, but no rule can be read or
            cited, so anything flagged is being handed to a human.
          </p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4">
        <span className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5 items-center justify-center">
            <span
              className="breathe absolute inset-0 rounded-full"
              style={{
                background: tierStatus.degraded ? "var(--warn)" : "var(--ok)",
                opacity: 0.5,
              }}
            />
            <Radio
              size={11}
              className="relative"
              style={{ color: tierStatus.degraded ? "var(--warn)" : "var(--ok)" }}
            />
          </span>
          <Label className="!text-[11px]">Live</Label>
        </span>

        <Tier label="Deterministic" value={tierStatus.deterministic} color="var(--ok)" />
        <Tier label="Retrieval" value={tierStatus.retrieval} color="var(--info)" />
        <Tier label="Reasoning" value={tierStatus.reasoning} color="var(--accent)" />
        {tierStatus.provider_chain && tierStatus.provider_chain.length > 1 ? (
          <ProviderChain
            chain={tierStatus.provider_chain}
            servedBy={tierStatus.served_by ?? ""}
            degraded={tierStatus.degraded}
          />
        ) : null}
        <Tier label="Orchestration" value={tierStatus.orchestration} color="var(--warn)" />

        <span className="mono ml-auto text-[11px] text-[var(--ink-3)]">{evaluationId}</span>
      </div>

      {audit ? (
        <div className="px-5 pb-4">
          <Disclosure
            summary={
              <span className="flex items-center gap-2">
                <Link2 size={13} className="text-[var(--ink-3)]" />
                <span className="mono text-[12px]">{audit.audit_ref}</span>
              </span>
            }
            hint={`${audit.steps.length} logged steps, each one sealed to the last`}
            right={
              <span className="flex items-center gap-2 pr-1">
                <Lock size={12} style={{ color: audit.chain_valid ? "var(--ok)" : "var(--bad)" }} />
                <span
                  className="text-[12px]"
                  style={{ color: audit.chain_valid ? "var(--ok)" : "var(--bad)" }}
                >
                  {audit.chain_valid ? (
                    <Term k="hash-chained">chain verified</Term>
                  ) : (
                    "CHAIN BROKEN"
                  )}
                </span>
              </span>
            }
          >
            <div className="glass-2 overflow-hidden">
              <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
                {/* Identifiers, printed. A model id is not a status and does
                    not belong in a status shape -- and `Tag` upper-cases,
                    which would mangle it. */}
                <span className="mono text-[11px] text-[var(--ink-2)]">{audit.provider}</span>
                <span className="mono text-[11px] text-[var(--ink-3)]">{audit.model_id}</span>
              </div>
              <div className="max-h-72 overflow-auto">
                <table className="w-full border-collapse text-left">
                  <thead className="sticky top-0" style={{ background: "color-mix(in oklab, var(--void-deep) 92%, transparent)" }}>
                    <tr className="label [&>th]:px-3 [&>th]:py-2 [&>th]:font-medium">
                      <th>#</th>
                      <th>Step</th>
                      <th>Tier</th>
                      <th>Detail</th>
                      <th>Entry hash</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.steps.map((step) => (
                      <tr
                        key={step.seq}
                        className="border-t border-white/[0.06] align-top text-[12px]"
                      >
                        <td className="mono px-3 py-2 text-[var(--ink-3)]">{step.seq}</td>
                        <td className="mono px-3 py-2 font-medium text-[var(--ink)]">{step.step}</td>
                        <td className="px-3 py-2 text-[var(--ink-3)]">{step.tier}</td>
                        <td className="px-3 py-2 leading-snug text-[var(--ink-2)]">{step.detail}</td>
                        <td className="mono px-3 py-2 text-[var(--ink-3)]">
                          {step.entry_hash.slice(0, 12)}…
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Disclosure>
        </div>
      ) : null}
    </GlassCard>
  );
}

function Tier({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span className="flex items-center gap-2">
      <span
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: color, boxShadow: `0 0 7px ${color}` }}
      />
      <Label className="!text-[11px]">{label}</Label>
      <span className="mono text-[12px] text-[var(--ink-2)]">{value}</span>
    </span>
  );
}

/**
 * Which providers were tried, and which one answered.
 *
 * Shown whenever there is more than one link, because a fallback that is not
 * visible is a system quietly telling the operator less than it knows. The link
 * that served is marked; the ones passed over are struck through, so "watsonx
 * was unreachable and Granite answered locally" reads at a glance rather than
 * requiring the audit trail to be opened.
 */
function ProviderChain({
  chain,
  servedBy,
  degraded,
}: {
  chain: string[];
  servedBy: string;
  degraded: boolean;
}) {
  // served_by is a provider's own name ("ollama-granite"); the chain holds
  // configured keys ("ollama"). Match on prefix rather than equality.
  const servedIndex = chain.findIndex((name) => servedBy.startsWith(name));

  return (
    <span className="flex items-center gap-2" title={`Provider chain: ${chain.join(" → ")}`}>
      <span
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: degraded ? "var(--warn)" : "var(--accent)" }}
      />
      <Label className="!text-[11px]">Chain</Label>
      <span className="mono flex items-center gap-1.5 text-[12px]">
        {chain.map((name, index) => (
          <span key={name} className="flex items-center gap-1.5">
            {index > 0 ? <span className="text-[var(--ink-3)]">→</span> : null}
            <span
              className={clsx(
                index === servedIndex && "font-medium",
                servedIndex >= 0 && index < servedIndex && "line-through opacity-50",
              )}
              style={{
                color:
                  index === servedIndex
                    ? degraded
                      ? "var(--warn)"
                      : "var(--ok)"
                    : "var(--ink-2)",
              }}
            >
              {name}
            </span>
          </span>
        ))}
      </span>
    </span>
  );
}
