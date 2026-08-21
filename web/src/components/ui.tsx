"use client";

import clsx from "clsx";
import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { ChevronDown, X } from "lucide-react";

/* --------------------------------------------------------------------------
   Tone
   --------------------------------------------------------------------------
   One map from a state name to a colour, so a risk level rendered in two
   places cannot drift into two colours. Every status string the API can emit
   resolves here; anything unknown resolves to ink rather than to a fallback
   colour that would read as a state of its own.
   -------------------------------------------------------------------------- */

export type Tone = "ok" | "warn" | "bad" | "crit" | "info" | "iris" | "neutral";

export const TONE_VAR: Record<Tone, string> = {
  ok: "var(--ok)",
  warn: "var(--warn)",
  bad: "var(--bad)",
  crit: "var(--crit)",
  info: "var(--info)",
  iris: "var(--iris)",
  neutral: "var(--ink-2)",
};

/** API status/risk vocabulary → tone. */
export const STATE_TONE: Record<string, Tone> = {
  nominal: "ok",
  low: "ok",
  watch: "warn",
  elevated: "warn",
  moderate: "warn",
  degraded: "bad",
  critical: "crit",
  high: "bad",
  medium: "warn",
  insufficient: "bad",
};

export function toneOf(state: string | null | undefined): Tone {
  return (state && STATE_TONE[state]) || "neutral";
}

export const STATUS_COLOR: Record<string, string> = {
  nominal: "var(--ok)",
  watch: "var(--warn)",
  degraded: "var(--bad)",
  elevated: "var(--warn)",
  critical: "var(--crit)",
};

/* --------------------------------------------------------------------------
   Surfaces
   -------------------------------------------------------------------------- */

export function GlassCard({
  children,
  className,
  live,
  interactive,
  loading,
  style,
}: {
  children?: ReactNode;
  className?: string;
  /** The one surface asking to be read next. At most one at a time. */
  live?: boolean;
  interactive?: boolean;
  loading?: boolean;
  style?: CSSProperties;
}) {
  return (
    <div
      style={style}
      className={clsx(
        "glass",
        live && "glass-live",
        interactive && "glass-interactive",
        loading && "loading-sheen",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("label", className)}>{children}</div>;
}

/* --------------------------------------------------------------------------
   Chip
   --------------------------------------------------------------------------
   Tinted glass rather than an outlined rectangle. The fill carries the tone at
   low alpha and the text carries it at full strength, which keeps a row of
   chips legible without any one of them shouting.
   -------------------------------------------------------------------------- */

export function Chip({
  children,
  tone = "neutral",
  icon,
  solid,
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  icon?: ReactNode;
  /** For the single most important state on screen. */
  solid?: boolean;
  className?: string;
}) {
  const color = TONE_VAR[tone];
  return (
    <span
      className={clsx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[11.5px] font-medium leading-tight tracking-[0.02em]",
        className,
      )}
      style={{
        color: tone === "neutral" ? "var(--ink-2)" : color,
        background: solid
          ? `color-mix(in oklab, ${color} 20%, transparent)`
          : "rgba(255,255,255,0.06)",
        boxShadow: `inset 0 0 0 1px ${
          tone === "neutral" ? "rgba(255,255,255,0.12)" : `color-mix(in oklab, ${color} 34%, transparent)`
        }`,
      }}
    >
      {icon}
      {children}
    </span>
  );
}

/** Kept under its v1 name; anything still importing `Tag` gets the new chip. */
export function Tag({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad" | "info";
}) {
  const map: Record<string, Tone> = {
    neutral: "neutral",
    good: "ok",
    warn: "warn",
    bad: "bad",
    info: "info",
  };
  return <Chip tone={map[tone]}>{children}</Chip>;
}

export function StatusDot({ status, pulse }: { status: string; pulse?: boolean }) {
  const color = STATUS_COLOR[status] ?? "var(--ink-3)";
  return (
    <span className="relative inline-flex h-2.5 w-2.5 shrink-0 items-center justify-center">
      {pulse ? (
        <span
          className="breathe absolute inset-0 rounded-full"
          style={{ background: color, opacity: 0.5 }}
        />
      ) : null}
      <span
        className="relative h-2 w-2 rounded-full"
        style={{ background: color, boxShadow: `0 0 10px ${color}` }}
      />
    </span>
  );
}

/* --------------------------------------------------------------------------
   Readouts
   -------------------------------------------------------------------------- */

export function StatTile({
  label,
  value,
  unit,
  sub,
  tone,
  className,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  tone?: Tone;
  className?: string;
}) {
  return (
    <div className={clsx("glass-2 px-3 py-2.5", className)}>
      <div className="label text-[10.5px]">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <span
          className="readout text-[22px] leading-none"
          style={{ color: tone ? TONE_VAR[tone] : "var(--ink)" }}
        >
          {value}
        </span>
        {unit ? <span className="text-[12px] text-[var(--ink-3)]">{unit}</span> : null}
      </div>
      {sub ? <div className="mt-1.5 text-[11.5px] leading-snug text-[var(--ink-3)]">{sub}</div> : null}
    </div>
  );
}

/** v1's `Stat`, kept so nothing that imports it breaks. */
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
    <div className="glass-2 px-3 py-2.5">
      <div className="label text-[10.5px]">{label}</div>
      <div className="readout mt-1.5 text-[20px] leading-none" style={{ color: tone ?? "var(--ink)" }}>
        {value}
      </div>
      {sub ? <div className="mt-1.5 text-[11px] text-[var(--ink-3)]">{sub}</div> : null}
    </div>
  );
}

/**
 * A bar. The fill is a gradient from a dimmed to a full-strength tone so it
 * reads as illuminated rather than painted, and the threshold marker is a
 * notch cut through it rather than a line drawn over it.
 */
export function Meter({
  value,
  max = 1,
  color = "var(--info)",
  threshold,
  height = 6,
  className,
}: {
  value: number;
  max?: number;
  color?: string;
  threshold?: number;
  height?: number;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      className={clsx("relative w-full overflow-hidden rounded-full", className)}
      style={{ height, background: "rgba(255,255,255,0.08)" }}
    >
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{
          width: `${pct}%`,
          background: `linear-gradient(90deg, color-mix(in oklab, ${color} 45%, transparent), ${color})`,
          boxShadow: `0 0 12px -2px ${color}`,
        }}
      />
      {threshold !== undefined ? (
        <div
          className="absolute top-0 h-full w-[2px] rounded-full bg-[var(--void-deep)]"
          style={{ left: `${Math.min(100, (threshold / max) * 100)}%` }}
        />
      ) : null}
    </div>
  );
}

/**
 * An alertness ring.
 *
 * A dial rather than a bar, because a bar invites reading the number and a dial
 * invites reading the state — which is the right first read for a rail of six
 * people you are scanning, not studying.
 */
export function Ring({
  value,
  size = 44,
  stroke = 3.5,
  tone = "ok",
  children,
}: {
  value: number;
  size?: number;
  stroke?: number;
  tone?: Tone;
  children?: ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, value));
  const color = TONE_VAR[tone];
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.11)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - clamped)}
          style={{ filter: `drop-shadow(0 0 5px ${color})`, transition: "stroke-dashoffset .8s cubic-bezier(.16,1,.3,1)" }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center">{children}</span>
    </span>
  );
}

/* --------------------------------------------------------------------------
   Disclosure
   --------------------------------------------------------------------------
   The mechanism the whole information architecture rests on: everything a
   specialist needs is still here, one deliberate click away, instead of on
   screen at all times competing with the answer.
   -------------------------------------------------------------------------- */

export function Disclosure({
  summary,
  hint,
  children,
  defaultOpen = false,
  right,
}: {
  summary: ReactNode;
  hint?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  right?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={id}
        className="selectable flex w-full items-center gap-3 rounded-[var(--radius-sm)] px-4 py-3 text-left"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-[13.5px] font-medium text-[var(--ink)]">{summary}</span>
          {hint ? (
            <span className="mt-0.5 block text-[12px] leading-snug text-[var(--ink-3)]">{hint}</span>
          ) : null}
        </span>
        {right}
        <ChevronDown
          size={16}
          className={clsx(
            "shrink-0 text-[var(--ink-3)] transition-transform duration-300",
            open && "rotate-180",
          )}
        />
      </button>
      {open ? (
        <div id={id} className="rise pt-3">
          {children}
        </div>
      ) : null}
    </div>
  );
}

/* --------------------------------------------------------------------------
   Sheet
   --------------------------------------------------------------------------
   A modal that behaves like one: labelled to assistive tech, closed by Escape
   and by the backdrop, focus moved in on open and returned on close, and the
   page behind it locked so it cannot scroll away under the overlay. v1's
   corpus browser was a fixed div — visually a dialog, and none of the above.
   -------------------------------------------------------------------------- */

export function Sheet({
  open,
  onClose,
  title,
  hint,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  hint?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const restoreTo = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;

    restoreTo.current = document.activeElement as HTMLElement | null;
    panel.current?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      // Keep Tab inside the sheet. Without this, tabbing walks out of the
      // dialog into a page the user cannot see.
      if (event.key !== "Tab" || !panel.current) return;
      const focusable = panel.current.querySelectorAll<HTMLElement>(
        'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      restoreTo.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-6"
      style={{ background: "rgba(4,3,12,0.62)", backdropFilter: "blur(10px)" }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="glass rise my-6 w-full max-w-4xl outline-none"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <header className="flex items-start gap-4 px-6 pb-4 pt-5">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="display text-[26px] text-[var(--ink)]">
              {title}
            </h2>
            {hint ? (
              <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-[var(--ink-2)]">{hint}</p>
            ) : null}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="glass-3 glass-interactive shrink-0 rounded-full p-2 text-[var(--ink-2)] hover:text-[var(--ink)]"
          >
            <X size={15} />
          </button>
        </header>
        <div className="px-6 pb-6">{children}</div>
        {footer}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------
   v1 compatibility
   -------------------------------------------------------------------------- */

/** The v1 zone panel, restyled onto glass. */
export function Panel({
  zone,
  title,
  hint,
  right,
  children,
  className,
}: {
  zone?: string;
  title: string;
  hint?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("glass flex flex-col overflow-hidden", className)}>
      <header className="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
        <div className="min-w-0">
          {zone ? <Label>{zone}</Label> : null}
          <h2 className="mt-1 text-[16px] font-medium tracking-[-0.01em] text-[var(--ink)]">
            {title}
          </h2>
          {hint ? (
            <p className="mt-1.5 text-[12.5px] leading-snug text-[var(--ink-3)]">{hint}</p>
          ) : null}
        </div>
        {right}
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

/* --------------------------------------------------------------------------
   Time
   -------------------------------------------------------------------------- */

export function utcTime(iso: string) {
  return new Date(iso).toISOString().slice(11, 16) + "Z";
}

export function utcDateTime(iso: string) {
  return new Date(iso).toISOString().slice(0, 16).replace("T", " ") + "Z";
}

/** Hours since a window start, as a float. Used to place things on a dial. */
export function hoursSince(windowStart: string, iso: string) {
  return (new Date(iso).getTime() - new Date(windowStart).getTime()) / 3_600_000;
}
