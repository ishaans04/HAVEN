"use client";

import { useState } from "react";
import clsx from "clsx";
import { ChevronDown, Info } from "lucide-react";
import type { ScenarioSummary } from "@/lib/types";

export function ScenarioBar({
  scenarios,
  selected,
  onSelect,
  note,
  loading,
}: {
  scenarios: ScenarioSummary[];
  selected: string;
  onSelect: (id: string) => void;
  note: string;
  loading: boolean;
}) {
  const [showHonesty, setShowHonesty] = useState(false);
  const active = scenarios.find((s) => s.id === selected);

  return (
    <header className="border-b border-[var(--hv-line)] bg-[var(--hv-panel)]/70 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-[17px] font-semibold tracking-[-0.02em]">HAVEN</span>
          <span className="hidden text-[10px] uppercase tracking-[0.18em] text-[var(--hv-dim)] sm:inline">
            Human Adaptation &amp; Vitality Enhancement Network
          </span>
        </div>

        <span className="hidden h-4 w-px bg-[var(--hv-line-bright)] sm:block" />

        <p className="hidden text-[11px] text-[var(--hv-muted)] lg:block">
          Fatigue-aware safety co-pilot · the maths owns the numbers, the AI owns the rulebook, the
          human owns the decision
        </p>

        <button
          onClick={() => setShowHonesty((v) => !v)}
          className="ml-auto flex items-center gap-1.5 rounded border border-[var(--hv-line-bright)] px-2 py-1 text-[10px] text-[var(--hv-muted)] transition-colors hover:text-[var(--hv-text)]"
        >
          <Info size={11} />
          Real vs simulated
          <ChevronDown size={11} className={clsx("transition-transform", showHonesty && "rotate-180")} />
        </button>
      </div>

      {showHonesty ? (
        <div className="grid gap-3 border-t border-[var(--hv-line)] px-4 py-3 text-[11px] leading-relaxed sm:grid-cols-2">
          <div>
            <div className="hv-zone-label mb-1">Real</div>
            <p className="text-[var(--hv-muted)]">
              The Three-Process Model of Alertness and NASA-TLX are the published models, computed
              from the inputs shown. The retrieval, precondition-checked rule selection, refusal
              path, deterministic screens, and hash-chained audit trail all execute live on every
              evaluation.
            </p>
          </div>
          <div>
            <div className="hv-zone-label mb-1">Simulated and labelled</div>
            <p className="text-[var(--hv-muted)]">
              The crew roster is representative, not real individuals. Sleep, duty, and task
              timelines are synthetic — no public live crew-timeline feed exists. The procedure
              corpus follows NASA flight-rule structure but its text is written for this prototype.
              The reasoning model is a scripted Granite stand-in so the console runs offline;
              watsonx.ai and Ollama adapters are wired behind the same interface.
            </p>
          </div>
        </div>
      ) : null}

      <div className="flex gap-1.5 overflow-x-auto border-t border-[var(--hv-line)] px-4 py-2">
        {scenarios.map((scenario) => (
          <button
            key={scenario.id}
            onClick={() => onSelect(scenario.id)}
            disabled={loading}
            className={clsx(
              "shrink-0 rounded border px-2.5 py-1.5 text-left transition-colors disabled:opacity-60",
              scenario.id === selected
                ? "border-[color:var(--hv-accent)] bg-[color:var(--hv-accent)]/[0.1]"
                : "border-[var(--hv-line)] hover:border-[var(--hv-line-bright)]",
            )}
          >
            <span
              className={clsx(
                "block text-[11px] font-medium",
                scenario.id === selected ? "text-[color:var(--hv-accent)]" : "text-[var(--hv-text)]",
              )}
            >
              {scenario.subtitle}
            </span>
            <span className="mono block text-[9px] text-[var(--hv-dim)]">{scenario.id}</span>
          </button>
        ))}
      </div>

      {active ? (
        <div className="border-t border-[var(--hv-line)] px-4 py-2.5">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="text-[12px] font-semibold">{active.title}</span>
            <span className="text-[10px] uppercase tracking-wider text-[color:var(--hv-accent)]">
              {active.demonstrates}
            </span>
          </div>
          <p className="mt-1 max-w-4xl text-[11px] leading-relaxed text-[var(--hv-muted)]">
            {note || active.note}
          </p>
        </div>
      ) : null}
    </header>
  );
}
