"use client";

import clsx from "clsx";
import type { ReactNode } from "react";

export function Panel({
  zone,
  title,
  hint,
  right,
  children,
  className,
}: {
  zone: string;
  title: string;
  hint?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("hv-panel flex flex-col overflow-hidden", className)}>
      <header className="flex items-start justify-between gap-3 border-b border-[var(--hv-line)] px-4 py-3">
        <div className="min-w-0">
          <div className="hv-zone-label">{zone}</div>
          <h2 className="mt-0.5 text-[13px] font-semibold tracking-tight text-[var(--hv-text)]">
            {title}
          </h2>
          {hint ? (
            <p className="mt-1 text-[11px] leading-snug text-[var(--hv-muted)]">{hint}</p>
          ) : null}
        </div>
        {right}
      </header>
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  );
}

export const STATUS_COLOR: Record<string, string> = {
  nominal: "var(--hv-nominal)",
  watch: "var(--hv-watch)",
  degraded: "var(--hv-degraded)",
  elevated: "var(--hv-watch)",
  critical: "var(--hv-critical)",
};

export function StatusDot({ status, pulse }: { status: string; pulse?: boolean }) {
  return (
    <span
      className={clsx("inline-block h-2 w-2 shrink-0 rounded-full", pulse && "hv-pulse")}
      style={{
        background: STATUS_COLOR[status] ?? "var(--hv-dim)",
        boxShadow: `0 0 8px ${STATUS_COLOR[status] ?? "transparent"}`,
      }}
    />
  );
}

export function Tag({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad" | "info";
}) {
  const tones: Record<string, string> = {
    neutral: "border-[var(--hv-line-bright)] text-[var(--hv-muted)]",
    good: "border-[color:var(--hv-nominal)] text-[color:var(--hv-nominal)]",
    warn: "border-[color:var(--hv-watch)] text-[color:var(--hv-watch)]",
    bad: "border-[color:var(--hv-degraded)] text-[color:var(--hv-degraded)]",
    info: "border-[color:var(--hv-accent)] text-[color:var(--hv-accent)]",
  };
  return (
    <span
      className={clsx(
        "mono inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

/** A labelled bar. Used for alertness, workload, and retrieval relevance. */
export function Meter({
  value,
  max = 1,
  color = "var(--hv-accent)",
  threshold,
  height = 6,
}: {
  value: number;
  max?: number;
  color?: string;
  threshold?: number;
  height?: number;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      className="relative w-full overflow-hidden rounded-full bg-[var(--hv-line)]"
      style={{ height }}
    >
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, background: color }}
      />
      {threshold !== undefined ? (
        <div
          className="absolute top-0 h-full w-px bg-[var(--hv-text)] opacity-60"
          style={{ left: `${Math.min(100, (threshold / max) * 100)}%` }}
          title={`threshold ${threshold}`}
        />
      ) : null}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="rounded border border-[var(--hv-line)] bg-[var(--hv-panel-raised)] px-2.5 py-2">
      <div className="hv-zone-label">{label}</div>
      <div
        className="mono mt-1 text-[15px] font-semibold leading-none"
        style={{ color: tone ?? "var(--hv-text)" }}
      >
        {value}
      </div>
      {sub ? <div className="mt-1 text-[10px] text-[var(--hv-dim)]">{sub}</div> : null}
    </div>
  );
}

export function utcTime(iso: string) {
  return new Date(iso).toISOString().slice(11, 16) + "Z";
}

export function utcDateTime(iso: string) {
  return new Date(iso).toISOString().slice(0, 16).replace("T", " ") + "Z";
}
