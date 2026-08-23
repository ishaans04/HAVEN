"use client";

import { useEffect, useId, useRef } from "react";
import { ArrowRight, X } from "lucide-react";
import type { ScenarioSummary } from "@/lib/types";
import { ASK } from "@/lib/ask";
import { DIVERGENT } from "./ArgumentWalk";

/**
 * The question chooser.
 *
 * This replaces a 581px dropdown listing eight scenario ids — a menu taller than
 * two thirds of the screen, met before the reader had seen a single number, and
 * written in the engine's vocabulary rather than anyone else's.
 *
 * The cases have not changed. What changed is that each one now states the
 * question it answers, so choosing between them is a matter of curiosity rather
 * than of decoding. "What happens when no rule covers it?" is a thing a person
 * wants to know. `no_procedure` is a thing a person has to be taught.
 *
 * Two of the eight carry a flag, and it is the flag that sells the project: on
 * those cases the deterministic checker throws out the retrieval tier's
 * top-scoring match. Anybody who opens only one case should be pointed at those.
 */
export function AskScreen({
  scenarios,
  selected,
  onSelect,
  onClose,
}: {
  scenarios: ScenarioSummary[];
  selected: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
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
      className="fixed inset-0 z-[60] overflow-y-auto"
      style={{
        background: "color-mix(in oklab, var(--void-deep) 78%, transparent)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
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
        className="mx-auto min-h-full w-full max-w-[1100px] px-5 py-10 outline-none sm:px-8 sm:py-16"
      >
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="display text-[26px] sm:text-[34px]">
              Ask HAVEN about a crew decision
            </h2>
            <p className="mt-2 max-w-xl text-[14px] leading-relaxed text-[var(--ink-2)]">
              Eight real situations, each one evaluated live. Two of them are worth
              your time before the rest.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="glass-3 glass-interactive shrink-0 rounded-full p-2.5 text-[var(--ink-2)] hover:text-[var(--ink)]"
          >
            <X size={16} />
          </button>
        </div>

        <ul className="mt-8 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(330px,1fr))]">
          {scenarios.map((scenario, i) => {
            const copy = ASK[scenario.id];
            const on = scenario.id === selected;
            const flagged = DIVERGENT.has(scenario.id);
            return (
              <li key={scenario.id}>
                <button
                  onClick={() => {
                    onSelect(scenario.id);
                    onClose();
                  }}
                  aria-current={on ? "true" : undefined}
                  className="ask-card rise group flex h-full w-full flex-col items-start gap-2 p-5 text-left"
                  style={{
                    animationDelay: `${Math.min(i, 8) * 35}ms`,
                    ...(on
                      ? {
                          background: "color-mix(in oklab, var(--accent) 10%, transparent)",
                          boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--accent) 40%, transparent)",
                        }
                      : {}),
                  }}
                >
                  {flagged ? (
                    <span
                      className="rounded-full px-2.5 py-[3px] text-[11px] font-medium"
                      style={{
                        color: "var(--warn)",
                        background: "color-mix(in oklab, var(--warn) 13%, transparent)",
                        boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--warn) 32%, transparent)",
                      }}
                    >
                      the checker overrules the AI
                    </span>
                  ) : null}

                  <span
                    className="text-[17px] font-medium leading-snug tracking-[-0.01em]"
                    style={{ color: on ? "var(--accent)" : "var(--ink)" }}
                  >
                    {copy?.question ?? scenario.title}
                  </span>

                  <span className="text-[13px] leading-relaxed text-[var(--ink-3)]">
                    {copy?.why ?? scenario.note}
                  </span>

                  <span className="mt-auto flex items-center gap-1.5 pt-3 text-[12px] font-medium text-[var(--ink-3)] transition-colors group-hover:text-[var(--accent)]">
                    {on ? "Showing this one" : "Ask this"}
                    <ArrowRight
                      size={13}
                      className="transition-transform duration-300 group-hover:translate-x-1"
                    />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
