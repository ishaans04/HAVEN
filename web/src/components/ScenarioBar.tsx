"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { BookOpen, Check, ChevronDown, Compass, Info, MoreHorizontal, Orbit, Route } from "lucide-react";
import type { ScenarioSummary } from "@/lib/types";
import { DIVERGENT } from "./ArgumentWalk";
import { Label } from "./ui";

/**
 * The masthead.
 *
 * It used to offer twelve controls — eight scenario pills and four utility
 * buttons — every one of them met before the reader saw a single number. That
 * is more decisions than the console asks of an operator in a whole session,
 * and it made the busiest thing on screen the part that carries no data.
 *
 * Three now. A scenario picker naming where you are, the tour, and an overflow
 * for everything consulted rarely. The seven other scenarios did not go
 * anywhere; they moved one click inside the picker, where each one can finally
 * afford to say what it demonstrates instead of being compressed into a pill.
 */
export function ScenarioBar({
  scenarios,
  selected,
  onSelect,
  note,
  loading,
  onOpenProcedures,
  onStartTour,
  walking,
  onStartWalk,
}: {
  scenarios: ScenarioSummary[];
  selected: string;
  onSelect: (id: string) => void;
  note: string;
  loading: boolean;
  onOpenProcedures: () => void;
  onStartTour: () => void;
  walking: boolean;
  onStartWalk: () => void;
}) {
  const active = scenarios.find((s) => s.id === selected);

  return (
    <header
      className="sticky top-0 z-40"
      style={{
        background: "rgba(7,6,20,0.66)",
        backdropFilter: "blur(26px) saturate(170%)",
        WebkitBackdropFilter: "blur(26px) saturate(170%)",
        boxShadow: "inset 0 -1px 0 rgba(255,255,255,0.08)",
      }}
    >
      <div className="mx-auto flex max-w-[1560px] flex-wrap items-center gap-x-5 gap-y-3 px-5 py-4 sm:px-8">
        <div className="flex items-baseline gap-3">
          <h1 className="display text-[21px] tracking-[-0.03em] text-[var(--ink)]">
            <span className="em">HAVEN</span>
          </h1>
          <span className="hidden text-[11px] uppercase tracking-[0.2em] text-[var(--ink-3)] lg:inline">
            Fatigue-aware safety co-pilot
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <ScenarioPicker
            scenarios={scenarios}
            selected={selected}
            onSelect={onSelect}
            loading={loading}
          />
          {!walking ? (
            <button
              onClick={onStartWalk}
              className="glass-interactive flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-medium"
              style={{
                color: "var(--ok)",
                background: "color-mix(in oklab, var(--ok) 14%, transparent)",
                boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--ok) 40%, transparent)",
              }}
            >
              <Route size={13} />
              <span className="hidden sm:inline">See the argument</span>
              <span className="sm:hidden">Argument</span>
            </button>
          ) : null}
          <BarButton onClick={onStartTour} icon={<Compass size={13} />}>
            Tour
          </BarButton>
          <Overflow onOpenProcedures={onOpenProcedures} />
        </div>
      </div>

      {active ? (
        <div className="mx-auto max-w-[1560px] px-5 pb-4 sm:px-8">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
            <h2 className="text-[16px] font-medium tracking-[-0.01em] text-[var(--ink)]">
              {active.title}
            </h2>
            <span className="mono text-[11px] text-[var(--ink-3)]">{active.id}</span>
          </div>
          <p className="mt-2 max-w-4xl text-[13px] leading-relaxed text-[var(--ink-3)]">
            {note || active.note}
          </p>
        </div>
      ) : null}
    </header>
  );
}

/* --------------------------------------------------------------------------
   The picker
   -------------------------------------------------------------------------- */

function ScenarioPicker({
  scenarios,
  selected,
  onSelect,
  loading,
}: {
  scenarios: ScenarioSummary[];
  selected: string;
  onSelect: (id: string) => void;
  loading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const active = scenarios.find((s) => s.id === selected);

  useDismiss(open, wrap, () => {
    setOpen(false);
    trigger.current?.focus();
  });

  return (
    <div ref={wrap} className="relative">
      <button
        ref={trigger}
        onClick={() => setOpen((v) => !v)}
        disabled={loading || !scenarios.length}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listId}
        className="glass-interactive flex items-center gap-2 rounded-full py-1.5 pl-3 pr-2.5 text-[13px] font-medium disabled:opacity-50"
        style={{
          color: "var(--iris)",
          background: "color-mix(in oklab, var(--iris) 14%, transparent)",
          boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--iris) 42%, transparent)",
        }}
      >
        <Orbit size={13} className="shrink-0" />
        <span className="max-w-[42vw] truncate sm:max-w-none">
          {active?.subtitle ?? "Scenario"}
        </span>
        <ChevronDown
          size={13}
          className={clsx("shrink-0 transition-transform duration-300", open && "rotate-180")}
        />
      </button>

      {open ? (
        <div
          id={listId}
          role="listbox"
          aria-label="Demonstration scenario"
          className="glass rise absolute right-0 z-50 mt-2 max-h-[70vh] w-[min(400px,calc(100vw-2.5rem))] overflow-y-auto p-2"
          style={{ borderRadius: "var(--radius)" }}
        >
          <Label className="px-3 pb-1 pt-2">Eight demonstration cases</Label>
          {scenarios.map((scenario) => {
            const on = scenario.id === selected;
            return (
              <button
                key={scenario.id}
                role="option"
                aria-selected={on}
                onClick={() => {
                  onSelect(scenario.id);
                  setOpen(false);
                  trigger.current?.focus();
                }}
                className="flex w-full items-start gap-2 rounded-[var(--radius-sm)] px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06]"
                style={on ? { background: "color-mix(in oklab, var(--iris) 12%, transparent)" } : undefined}
              >
                <span className="mt-[3px] w-3.5 shrink-0">
                  {on ? <Check size={13} className="text-[var(--iris)]" /> : null}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className="block text-[13px] font-medium"
                    style={{ color: on ? "var(--iris)" : "var(--ink)" }}
                  >
                    {scenario.subtitle}
                  </span>
                  <span className="mt-1 block text-[12px] leading-snug text-[var(--ink-3)]">
                    {scenario.title}
                  </span>
                  {DIVERGENT.has(scenario.id) ? (
                    <span
                      className="mt-2 inline-block rounded-full px-2 py-[2px] text-[11px] font-medium"
                      style={{
                        color: "var(--warn)",
                        background: "color-mix(in oklab, var(--warn) 12%, transparent)",
                        boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--warn) 30%, transparent)",
                      }}
                    >
                      the checker overrules the top match
                    </span>
                  ) : null}
                </span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

/* --------------------------------------------------------------------------
   The overflow
   -------------------------------------------------------------------------- */

function Overflow({ onOpenProcedures }: { onOpenProcedures: () => void }) {
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
 * The honesty statement, moved out of the masthead.
 *
 * It was an inline panel that pushed the whole console down when opened. It is
 * consulted once, by somebody deciding how much to believe, so it belongs in a
 * sheet rather than in the furniture of every screen.
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

function BarButton({
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
      onClick={onClick}
      className="glass-3 glass-interactive flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] text-[var(--ink-2)] hover:text-[var(--ink)]"
    >
      {icon}
      {children}
    </button>
  );
}
