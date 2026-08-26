"use client";

import clsx from "clsx";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { ChevronDown, X } from "lucide-react";
import { useFinePointer, useMotionOK, useReveal } from "@/lib/motion";
import { signal } from "@/lib/coach";

/* --------------------------------------------------------------------------
   Tone
   --------------------------------------------------------------------------
   One map from a state name to a colour, so a risk level rendered in two
   places cannot drift into two colours. Every status string the API can emit
   resolves here; anything unknown resolves to ink rather than to a fallback
   colour that would read as a state of its own.
   -------------------------------------------------------------------------- */

export type Tone = "ok" | "warn" | "bad" | "crit" | "info" | "accent" | "neutral";

export const TONE_VAR: Record<Tone, string> = {
  ok: "var(--ok)",
  warn: "var(--warn)",
  bad: "var(--bad)",
  crit: "var(--crit)",
  info: "var(--info)",
  accent: "var(--accent)",
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
  refuse,
  interactive,
  loading,
  sheen = true,
  style,
}: {
  children?: ReactNode;
  className?: string;
  /** The one surface asking to be read next. At most one at a time. */
  live?: boolean;
  /** The same emphasis as `live`, in the colour reserved for a stop. */
  refuse?: boolean;
  interactive?: boolean;
  loading?: boolean;
  /** The pointer-tracked specular highlight. On by default; off for surfaces
   *  that are already carrying a moving element of their own. */
  sheen?: boolean;
  style?: CSSProperties;
}) {
  const spec = useRef<HTMLSpanElement>(null);
  const frame = useRef(0);
  const motionOK = useMotionOK();
  const fine = useFinePointer();
  const live_ = live;

  // Written straight to custom properties rather than through state: a
  // highlight that re-renders React on every pointer move is a highlight that
  // costs more than it is worth.
  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const node = spec.current;
      if (!node) return;
      const box = event.currentTarget.getBoundingClientRect();
      const x = event.clientX - box.left;
      const y = event.clientY - box.top;
      if (frame.current) return;
      frame.current = requestAnimationFrame(() => {
        frame.current = 0;
        node.style.setProperty("--spec-x", `${x.toFixed(1)}px`);
        node.style.setProperty("--spec-y", `${y.toFixed(1)}px`);
      });
    },
    [],
  );

  useEffect(() => () => { if (frame.current) cancelAnimationFrame(frame.current); }, []);

  const withSheen = sheen && motionOK && fine;

  return (
    <div
      style={style}
      onPointerMove={withSheen ? onPointerMove : undefined}
      className={clsx(
        "glass",
        live_ && !refuse && "glass-live",
        refuse && "glass-refuse",
        interactive && "glass-interactive",
        loading && "loading-sheen",
        className,
      )}
    >
      {withSheen ? <span ref={spec} aria-hidden className="glass-spec" /> : null}
      {children}
    </div>
  );
}

/**
 * Reveal on scroll.
 *
 * A wrapper rather than a class, so the observer and the class that hides the
 * element are created by the same component — an element can never be left
 * hidden because somebody added `.reveal` and forgot to observe it.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  /** Milliseconds of stagger. Keep the whole group under ~300ms. */
  delay?: number;
  className?: string;
}) {
  const { ref, shown } = useReveal<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={clsx("reveal", shown && "reveal-in", className)}
      style={shown && delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}

export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("label", className)}>{children}</div>;
}

/**
 * One named reading in a register.
 *
 * The console kept saying things in capsules — a pill for the action, a pill
 * for the risk, a pill for the citation, a pill for the confidence — which is
 * the badge row every generated dashboard ships, and which never says what any
 * of the values *are*. A field names the reading, puts it underneath, and lets
 * a hairline do the separating. Colour is spent only where the value is a state
 * the engine actually reported.
 *
 * A hairline on the left rather than a box around each one: these are rows of
 * readings, and boxing them would put containers back on a page that spent a
 * whole pass getting down to three.
 */
export function Field({
  label,
  note,
  children,
  className,
}: {
  label: string;
  /** The provenance of the figure — the model or scale it came off. */
  note?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "min-w-0 border-l border-white/[0.09] pl-4 first:border-l-0 first:pl-0",
        className,
      )}
    >
      <dt className="label">{label}</dt>
      <dd className="mt-1.5 text-[13px] leading-snug">{children}</dd>
      {note ? (
        <dd className="mt-1 text-[11px] leading-snug text-[var(--ink-3)]">{note}</dd>
      ) : null}
    </div>
  );
}

/* --------------------------------------------------------------------------
   Tag
   --------------------------------------------------------------------------
   A ruled label, not a capsule.

   This was a tinted pill: rounded-full, a fill at low alpha, an inset ring.
   Six of them in a column is the single most recognisable shape in generated
   interface design, and a page arguing that its own reasoning is worth
   checking should not be wearing the house style of software that does not.
   The honesty ledger was the worst of it -- six identical lozenges stacked
   down the left of a table, all outline and no information.

   What replaces it is what a spec sheet does: micro-caps, letterspaced, and a
   short rule in the state's colour standing to the left. The rule is the
   marker; the type is the value. Nothing is enclosed, so nothing has to earn
   its enclosure.

   Contrast improves rather than suffers. The tinted fill was lifting the
   background under every one of these, and removing it puts the text back on
   the page's own near-black.

   `solid` is for the single most important state on a screen. It thickens the
   rule and lights it rather than filling a shape -- weight, not decoration,
   which is the same distinction selection uses everywhere else here.
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
  const neutral = tone === "neutral";
  return (
    <span
      className={clsx(
        "inline-flex shrink-0 items-center gap-[7px] text-[11px] font-medium uppercase leading-tight tracking-[0.13em]",
        className,
      )}
      style={{ color: neutral ? "var(--ink-2)" : color }}
    >
      <span
        aria-hidden
        className="shrink-0 rounded-[1px]"
        style={{
          width: solid ? 3 : 2,
          height: 11,
          background: neutral ? "rgba(255,255,255,0.28)" : color,
          boxShadow: solid ? `0 0 7px -1px ${color}` : undefined,
        }}
      />
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
  mark,
  children,
}: {
  value: number;
  size?: number;
  stroke?: number;
  tone?: Tone;
  /**
   * A reference value, drawn as a notch across the track.
   *
   * On the crew rail this is the operator's own baseline, and it is the
   * difference between a dial that reports a number and one that reports a
   * departure. "0.37" means nothing until you can see it sitting well inside
   * where that person normally runs.
   */
  mark?: number;
  children?: ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, value));
  const color = TONE_VAR[tone];
  const notch = (() => {
    if (mark === undefined) return null;
    const angle = Math.max(0, Math.min(1, mark)) * 2 * Math.PI;
    const inner = r - stroke / 2 - 1.5;
    const outer = r + stroke / 2 + 1.5;
    return {
      x1: size / 2 + inner * Math.cos(angle),
      y1: size / 2 + inner * Math.sin(angle),
      x2: size / 2 + outer * Math.cos(angle),
      y2: size / 2 + outer * Math.sin(angle),
    };
  })();
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
        {notch ? (
          <line
            x1={notch.x1}
            y1={notch.y1}
            x2={notch.x2}
            y2={notch.y2}
            stroke="var(--ink-2)"
            strokeWidth={1.25}
            strokeLinecap="round"
            opacity={0.75}
          />
        ) : null}
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
        onClick={() => {
          // Announced from the handler, never from inside the updater: a
          // state updater has to stay pure, and signalling in there fires a
          // setState on the tour in the middle of this component's own
          // update, which React is free to drop.
          if (!open) signal("evidence");
          setOpen((v) => !v);
        }}
        aria-expanded={open}
        aria-controls={id}
        className="disclosure"
      >
        <span className="min-w-0 flex-1">
          <span className="disclosure-title block text-[13px] font-medium">{summary}</span>
          {hint ? (
            <span className="mt-1 block text-[12px] leading-snug text-[var(--ink-3)]">{hint}</span>
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
        <div id={id} className="rise pb-4">
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
      style={{ background: "color-mix(in oklab, var(--void-deep) 62%, transparent)", backdropFilter: "blur(10px)" }}
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
            <p className="mt-2 text-[13px] leading-snug text-[var(--ink-3)]">{hint}</p>
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
