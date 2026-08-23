"use client";

import { useEffect } from "react";
import { ArrowLeft, ArrowRight, Route, X } from "lucide-react";
import { useSwipe } from "@/lib/motion";
import { Label } from "./ui";

/**
 * The demonstration, as an argument rather than a menu.
 *
 * Eight scenarios sat in a picker as equals, which is the right structure for
 * an operator and the wrong one for anybody being shown this for the first
 * time. Two of the eight carry the entire case — the near-miss the checker
 * catches, and the situation no rule governs — and nothing marked them out. A
 * reader with four minutes looked at the default case, saw a competent
 * recommendation, and left without meeting the behaviour that makes this
 * different from any other retrieval demo.
 *
 * Four beats, in the order the argument builds: it works, it discriminates, it
 * refuses, it degrades honestly. Each one says what to watch for before the
 * data lands, because a demonstration nobody knows how to read demonstrates
 * nothing.
 *
 * Deliberately separate from the tour. The tour explains the *console*; this
 * explains the *system*. Conflating them would leave a reader who already knows
 * the layout sitting through it again.
 */

export interface Beat {
  scenario: string;
  title: string;
  watch: string;
}

export const BEATS: Beat[] = [
  {
    scenario: "burn_fatigue",
    title: "It finds the rule",
    watch:
      "A commander six nights into restricted sleep, forty minutes from a reboost burn. The maths flags the collision, retrieval offers four candidate rules, and one of them survives the checker and gets cited. This is the ordinary case working.",
  },
  {
    scenario: "eva_near_miss",
    title: "It tells near-misses apart",
    watch:
      "Now watch the retrieval score. The top-ranked passage scores a perfect 1.000 and is the wrong rule. The checker rejects it on its preconditions and a different section governs. Ranking found the shortlist; it did not find the answer.",
  },
  {
    scenario: "no_procedure",
    title: "It refuses",
    watch:
      "Fatigue during a medical contingency. Nothing in the corpus governs it. The top match still scores 1.000, and a pipeline that cited its best hit would answer with a real section number for a situation no rule covers. This one stops and escalates instead. It is the most important thing here.",
  },
  {
    scenario: "provider_outage",
    title: "It fails honestly",
    watch:
      "The reasoning tier is unreachable. The deterministic scoring is unaffected and every figure is still real, but nothing can be cited without the rulebook being read, so the Situation escalates rather than being answered from the numbers alone.",
  },
];

/** Scenarios where ranking by score alone gets it wrong. Marked in the picker. */
export const DIVERGENT = new Set(["eva_near_miss", "no_procedure"]);

export function ArgumentWalk({
  index,
  onIndex,
  onClose,
}: {
  index: number;
  onIndex: (next: number) => void;
  onClose: () => void;
}) {
  const beat = BEATS[index];
  const last = index === BEATS.length - 1;

  const swipe = useSwipe<HTMLDivElement>(
    () => onIndex(Math.min(BEATS.length - 1, index + 1)),
    () => onIndex(Math.max(0, index - 1)),
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") onIndex(Math.min(BEATS.length - 1, index + 1));
      if (event.key === "ArrowLeft") onIndex(Math.max(0, index - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, onIndex, onClose]);

  return (
    // The sticky lives on a wrapper, not on the card. `.glass` sets
    // `position: relative` and this stylesheet loads after Tailwind's
    // utilities, so a `sticky` class on the same element loses silently and the
    // panel just scrolls away. The offset comes from `--masthead-h`, which the
    // console measures, because the masthead's height changes with the length
    // of each scenario's note.
    <div
      ref={swipe}
      className="sticky z-30 mb-4"
      style={{ top: "calc(var(--masthead-h, 150px) + 8px)" }}
      role="region"
      aria-label="Guided walk through the argument"
    >
      <div className="glass rise overflow-hidden">
      <div className="flex flex-wrap items-start gap-x-5 gap-y-3 p-5">
        <span
          className="mt-1 shrink-0 rounded-full p-2"
          style={{ color: "var(--accent)", background: "color-mix(in oklab, var(--accent) 14%, transparent)" }}
        >
          <Route size={15} />
        </span>

        <div className="min-w-[240px] flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <Label className="!text-[11px]">
              The argument · {index + 1} of {BEATS.length}
            </Label>
            <h2 className="text-[16px] font-medium text-[var(--ink)]">{beat.title}</h2>
          </div>
          <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-[var(--ink-2)]">
            {beat.watch}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => onIndex(index - 1)}
            disabled={index === 0}
            aria-label="Previous"
            className="glass-3 glass-interactive rounded-full p-2 text-[var(--ink-2)] hover:text-[var(--ink)] disabled:opacity-35"
          >
            <ArrowLeft size={14} />
          </button>
          {last ? (
            <button
              onClick={onClose}
              className="glass-interactive rounded-full px-4 py-2 text-[13px] font-medium"
              style={{
                color: "var(--ok)",
                background: "color-mix(in oklab, var(--ok) 16%, transparent)",
                boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--ok) 42%, transparent)",
              }}
            >
              Explore freely
            </button>
          ) : (
            <button
              onClick={() => onIndex(index + 1)}
              className="glass-interactive flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-medium"
              style={{
                color: "var(--accent)",
                background: "color-mix(in oklab, var(--accent) 16%, transparent)",
                boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--accent) 44%, transparent)",
              }}
            >
              Next
              <ArrowRight size={14} />
            </button>
          )}
          <button
            onClick={onClose}
            aria-label="Leave the walk"
            className="glass-3 glass-interactive rounded-full p-2 text-[var(--ink-2)] hover:text-[var(--ink)]"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Progress, as four segments rather than a bar: they are discrete beats
          and the reader can see how many are left. */}
      <div className="flex gap-1 px-5 pb-4" aria-hidden>
        {BEATS.map((b, i) => (
          <span
            key={b.scenario}
            className="h-[3px] flex-1 rounded-full transition-colors duration-300"
            style={{
              background: i <= index ? "var(--accent)" : "rgba(255,255,255,0.13)",
              boxShadow: i <= index ? "0 0 8px -2px var(--accent)" : undefined,
            }}
          />
        ))}
        </div>
      </div>
    </div>
  );
}
