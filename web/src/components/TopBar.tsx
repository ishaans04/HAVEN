"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { BookOpen, Compass, Info, MessageCircleQuestion, MoreHorizontal, Route } from "lucide-react";
import { Label } from "./ui";

/**
 * The bar.
 *
 * It was 184px tall — a fifth of the screen — before the reader met a single
 * number, and it carried a scenario picker, a zone nav, a title, an id and a
 * three-line note. Four navigation mechanisms competing above the fold, none of
 * them the content.
 *
 * Two controls now. "Ask another question" is the only way to change case, and
 * it opens a screen rather than a 581px dropdown, so each case can state the
 * question it answers instead of being compressed into a menu row. The guided
 * walk stays because it is the one thing a first-time reader most benefits from
 * and it disappears while it is running.
 *
 * The zone nav went entirely. It existed to navigate six simultaneous panels;
 * the console does not have six simultaneous panels any more.
 */
export function TopBar({
  onAsk,
  onOpenProcedures,
  onStartTour,
  walking,
  onStartWalk,
}: {
  onAsk: () => void;
  onOpenProcedures: () => void;
  onStartTour: () => void;
  walking: boolean;
  onStartWalk: () => void;
}) {
  return (
    <header
      className="sticky top-0 z-40"
      style={{
        background: "color-mix(in oklab, var(--void-deep) 62%, transparent)",
        backdropFilter: "blur(26px) saturate(170%)",
        WebkitBackdropFilter: "blur(26px) saturate(170%)",
        boxShadow: "inset 0 -1px 0 rgba(255,255,255,0.07)",
      }}
    >
      <div className="mx-auto flex max-w-[1400px] items-center gap-x-4 px-5 py-3 sm:px-8">
        <Link href="/" className="flex items-baseline gap-3">
          <span className="display text-[19px] tracking-[-0.03em] text-[var(--ink)]">
            <span className="em">HAVEN</span>
          </span>
          <span className="hidden text-[11px] uppercase tracking-[0.2em] text-[var(--ink-3)] lg:inline">
            Fatigue-aware safety co-pilot
          </span>
        </Link>

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={onAsk}
            className="glass-interactive flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-medium"
            style={{
              color: "var(--accent)",
              background: "color-mix(in oklab, var(--accent) 14%, transparent)",
              boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--accent) 42%, transparent)",
            }}
          >
            <MessageCircleQuestion size={13} />
            <span className="hidden sm:inline">Ask another question</span>
            <span className="sm:hidden">Ask</span>
          </button>

          {!walking ? (
            <button
              onClick={onStartWalk}
              className="glass-3 glass-interactive hidden shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-medium text-[var(--ink-2)] hover:text-[var(--ink)] sm:flex"
            >
              <Route size={13} />
              See the argument
            </button>
          ) : null}

          <Overflow onOpenProcedures={onOpenProcedures} onStartTour={onStartTour} />
        </div>
      </div>
    </header>
  );
}

/* --------------------------------------------------------------------------
   The overflow
   -------------------------------------------------------------------------- */

function Overflow({
  onOpenProcedures,
  onStartTour,
}: {
  onOpenProcedures: () => void;
  onStartTour: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [honesty, setHonesty] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useDismiss(open, wrap, () => {
    setOpen(false);
    trigger.current?.focus();
  });

  return (
    <>
      <div ref={wrap} className="relative">
        <button
          ref={trigger}
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-haspopup="menu"
          aria-controls={menuId}
          aria-label="More"
          className="glass-3 glass-interactive flex items-center rounded-full p-2 text-[var(--ink-2)] hover:text-[var(--ink)]"
        >
          <MoreHorizontal size={14} />
        </button>

        {open ? (
          <div
            id={menuId}
            role="menu"
            className="glass rise absolute right-0 z-50 mt-2 w-[240px] p-2"
            style={{ borderRadius: "var(--radius)" }}
          >
            <MenuItem
              icon={<Route size={13} />}
              onClick={() => {
                setOpen(false);
                onStartTour();
              }}
            >
              Tour the console
            </MenuItem>
            <MenuItem
              icon={<BookOpen size={13} />}
              onClick={() => {
                setOpen(false);
                onOpenProcedures();
              }}
            >
              The rulebook
            </MenuItem>
            <MenuItem
              icon={<Info size={13} />}
              onClick={() => {
                setOpen(false);
                setHonesty(true);
              }}
            >
              Real vs simulated
            </MenuItem>
            <Link
              href="/"
              role="menuitem"
              className="flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-3 py-2 text-left text-[13px] text-[var(--ink-2)] transition-colors hover:bg-white/[0.06] hover:text-[var(--ink)]"
            >
              <Compass size={13} />
              What this is
            </Link>
          </div>
        ) : null}
      </div>

      {honesty ? <HonestySheet onClose={() => setHonesty(false)} /> : null}
    </>
  );
}

function MenuItem({
  children,
  icon,
  onClick,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-3 py-2 text-left text-[13px] text-[var(--ink-2)] transition-colors hover:bg-white/[0.06] hover:text-[var(--ink)]"
    >
      {icon}
      {children}
    </button>
  );
}

/**
 * The honesty statement. Consulted once, by somebody deciding how much to
 * believe, so it belongs in a sheet rather than in the furniture of every
 * screen.
 */
function HonestySheet({ onClose }: { onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    panel.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[55] flex items-start justify-center overflow-y-auto p-4 sm:p-6"
      style={{
        background: "color-mix(in oklab, var(--void-deep) 62%, transparent)",
        backdropFilter: "blur(10px)",
      }}
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
        className="glass rise my-8 w-full max-w-3xl p-6 outline-none"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <h2 id={titleId} className="display text-[26px]">
          What is real here, and what is not
        </h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="glass-2 p-4">
            <Label className="!text-[11px]">Real, and running</Label>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-2)]">
              The Three-Process Model of Alertness and NASA-TLX are the published models, computed
              from the inputs shown. Retrieval, precondition-checked rule selection, the refusal
              path, the deterministic screens and the hash-chained audit trail all execute live on
              every evaluation.
            </p>
          </div>
          <div className="glass-2 p-4">
            <Label className="!text-[11px]">Simulated, and labelled</Label>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-2)]">
              The crew roster is representative, not real individuals. Sleep, duty and task
              timelines are synthetic. No public live crew-timeline feed exists. Where the corpus
              reports <span className="mono">prototype</span> authority, its text follows NASA
              flight-rule structure but was written for this build. The reasoning model is a
              scripted Granite stand-in unless a live provider is configured.
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="glass-3 glass-interactive mt-5 rounded-full px-4 py-2 text-[13px] text-[var(--ink)]"
        >
          Close
        </button>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------
   Shared dismissal
   --------------------------------------------------------------------------
   Escape and a click outside, both returning focus to whatever opened the
   thing. A popover you can only close by finding its trigger again is a
   popover that traps a keyboard.
   -------------------------------------------------------------------------- */

function useDismiss(
  open: boolean,
  wrap: React.RefObject<HTMLElement>,
  close: () => void,
) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onDown = (event: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(event.target as Node)) close();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [open, wrap, close]);
}
