"use client";

import { useState } from "react";
import clsx from "clsx";
import { BookOpen, ChevronDown, Info } from "lucide-react";
import type { ScenarioSummary } from "@/lib/types";
import { Chip, Label } from "./ui";

/**
 * The masthead: identity, the scenario picker, and the honesty panel.
 *
 * Sticky, translucent, and thin. It is the one surface that persists while the
 * console changes underneath it, so it has to stay quiet — the field shows
 * through it and the content below scrolls under it rather than past it.
 */
export function ScenarioBar({
  scenarios,
  selected,
  onSelect,
  note,
  loading,
  onOpenProcedures,
}: {
  scenarios: ScenarioSummary[];
  selected: string;
  onSelect: (id: string) => void;
  note: string;
  loading: boolean;
  onOpenProcedures: () => void;
}) {
  const [showHonesty, setShowHonesty] = useState(false);
  const active = scenarios.find((s) => s.id === selected);

  return (
    <header
      className="sticky top-0 z-40"
      style={{
        background: "rgba(7,6,20,0.62)",
        backdropFilter: "blur(26px) saturate(170%)",
        WebkitBackdropFilter: "blur(26px) saturate(170%)",
        boxShadow: "inset 0 -1px 0 rgba(255,255,255,0.08)",
      }}
    >
      <div className="mx-auto flex max-w-[1560px] flex-wrap items-center gap-x-5 gap-y-3 px-5 py-3.5 sm:px-8">
        <div className="flex items-baseline gap-3">
          <h1 className="display text-[21px] tracking-[-0.03em] text-[var(--ink)]">
            <span className="em">HAVEN</span>
          </h1>
          <span className="hidden text-[10.5px] uppercase tracking-[0.2em] text-[var(--ink-3)] lg:inline">
            Fatigue-aware safety co-pilot
          </span>
        </div>

        <p className="hidden max-w-md text-[12px] leading-snug text-[var(--ink-3)] xl:block">
          The maths owns the numbers · the AI reads the rulebook · the human owns the decision
        </p>

        <div className="ml-auto flex items-center gap-2">
          <BarButton onClick={onOpenProcedures} icon={<BookOpen size={13} />}>
            The rulebook
          </BarButton>
          <BarButton
            onClick={() => setShowHonesty((v) => !v)}
            icon={<Info size={13} />}
            expanded={showHonesty}
            chevron
          >
            Real vs simulated
          </BarButton>
        </div>
      </div>

      {showHonesty ? (
        <div
          className="rise mx-auto grid max-w-[1560px] gap-6 px-5 pb-5 sm:grid-cols-2 sm:px-8"
          id="honesty"
        >
          <div className="glass-2 px-4 py-3.5">
            <Label className="!text-[10.5px]" >Real</Label>
            <p className="mt-2 text-[12.5px] leading-relaxed text-[var(--ink-2)]">
              The Three-Process Model of Alertness and NASA-TLX are the published models, computed
              from the inputs shown. Retrieval, precondition-checked rule selection, the refusal
              path, the deterministic screens and the hash-chained audit trail all execute live on
              every evaluation.
            </p>
          </div>
          <div className="glass-2 px-4 py-3.5">
            <Label className="!text-[10.5px]">Simulated, and labelled</Label>
            <p className="mt-2 text-[12.5px] leading-relaxed text-[var(--ink-2)]">
              The crew roster is representative, not real individuals. Sleep, duty and task
              timelines are synthetic — no public live crew-timeline feed exists. Where the corpus
              reports <span className="mono">prototype</span> authority, its text follows NASA
              flight-rule structure but was written for this build. The reasoning model is a
              scripted Granite stand-in unless a live provider is configured.
            </p>
          </div>
        </div>
      ) : null}

      {/* Scenario rail. */}
      <div className="mx-auto max-w-[1560px] px-5 sm:px-8">
        <div className="fade-x no-bar flex gap-1.5 overflow-x-auto px-1 pb-3">
          {scenarios.map((scenario) => {
            const on = scenario.id === selected;
            return (
              <button
                key={scenario.id}
                onClick={() => onSelect(scenario.id)}
                disabled={loading}
                aria-pressed={on}
                className="selectable shrink-0 rounded-full px-3.5 py-1.5 text-left disabled:opacity-50"
              >
                <span
                  className="block whitespace-nowrap text-[12.5px] font-medium"
                  style={{ color: on ? "var(--iris)" : "var(--ink-2)" }}
                >
                  {scenario.subtitle}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {active ? (
        <div className="mx-auto max-w-[1560px] px-5 pb-4 sm:px-8">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
            <h2 className="text-[15px] font-medium tracking-[-0.01em] text-[var(--ink)]">
              {active.title}
            </h2>
            <Chip tone="iris">{active.demonstrates.toLowerCase()}</Chip>
            <span className="mono text-[11px] text-[var(--ink-3)]">{active.id}</span>
          </div>
          <p className="mt-1.5 max-w-4xl text-[12.5px] leading-relaxed text-[var(--ink-3)]">
            {note || active.note}
          </p>
        </div>
      ) : null}
    </header>
  );
}

function BarButton({
  children,
  icon,
  onClick,
  expanded,
  chevron,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  onClick: () => void;
  expanded?: boolean;
  chevron?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      aria-expanded={chevron ? expanded : undefined}
      aria-controls={chevron ? "honesty" : undefined}
      className="glass-3 glass-interactive flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-[12.5px] text-[var(--ink-2)] hover:text-[var(--ink)]"
    >
      {icon}
      {children}
      {chevron ? (
        <ChevronDown
          size={13}
          className={clsx("transition-transform duration-300", expanded && "rotate-180")}
        />
      ) : null}
    </button>
  );
}
