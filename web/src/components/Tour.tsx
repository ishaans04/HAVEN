"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, X } from "lucide-react";
import { useFinePointer, useSwipe } from "@/lib/motion";
import { onSignal, type Signal } from "@/lib/coach";
import { Label } from "./ui";

/**
 * The first-run walkthrough — four things to do, not four things to read.
 *
 * It used to be 181 words across four stops, the longest of them 58, asking
 * somebody to read a paragraph about a dial instead of turning it. That is the
 * same fault the console itself was pulled apart to fix, left sitting in the
 * one place every first-time reader is guaranteed to meet.
 *
 * So each stop now asks for a gesture and waits for it. The reader picks an
 * operator, hunts the ring for an hour below the line, drags the burn until it
 * clears, and unfolds the evidence — which is not a description of the console,
 * it is the console, and they leave knowing how to drive it. Thirty-odd words
 * total.
 *
 * Two consequences worth stating, because both are easy to get wrong:
 *
 * **The overlay must not swallow the page.** A tour that asks for a drag and
 * then eats the pointer is a tour nobody can complete, so the root is
 * `pointer-events-none` and only the card takes input. That also means this is
 * not a modal and must not claim to be one — `aria-modal` is gone, because the
 * rest of the page genuinely is available.
 *
 * **Not every gesture exists on every device.** Sweeping and dragging the dial
 * are fine-pointer only, by an earlier decision that keeps the 376px column
 * scrolling. On a touch screen those stops ask for nothing, say what the
 * instrument does instead, and advance on the button — rather than demanding a
 * gesture the build deliberately does not offer.
 */

const KEY = "haven.tour.v2";

interface Stop {
  target: string;
  title: string;
  /** The ask. One line, imperative, under a dozen words. */
  ask: string;
  /** What to say where the gesture is unavailable. Falls back to `ask`. */
  askCoarse?: string;
  /** The gesture that completes this stop. Absent means "read and continue". */
  done?: Signal;
  /** Shown for a beat once they have done it. */
  got?: string;
  /** Which side of the target the card prefers. */
  side: "right" | "left" | "below";
}

const STOPS: Stop[] = [
  {
    target: "crew",
    title: "Pick anyone",
    ask: "Choose an operator to put their day on the dial.",
    done: "crew",
    got: "That is their own baseline, not a group average.",
    side: "below",
  },
  {
    target: "dial",
    title: "Find the worst hour",
    ask: "Sweep the ring. Stop where the reading falls under 0.70.",
    askCoarse: "The band is predicted alertness — further out is sharper.",
    done: "trough",
    got: "That dip is the body clock, not a bad night.",
    side: "left",
  },
  {
    target: "dial",
    title: "Move the burn",
    ask: "Drag the flagged task until it clears the line.",
    askCoarse: "Each dot is a task, sitting at its hour and its alertness.",
    done: "cleared",
    got: "Same crew, same job. Only the hour changed.",
    side: "left",
  },
  {
    target: "audit",
    title: "Check it, do not trust it",
    ask: "Open a panel marked with a chevron.",
    done: "evidence",
    got: "Every step is logged and hash-chained. Nothing is hidden — it is folded.",
    side: "below",
  },
];

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  /** True once the current stop's gesture has been performed. */
  const [did, setDid] = useState(false);
  const finePointer = useFinePointer();

  // Touch's answer to the arrow keys. Same two actions, same bounds.
  const swipe = useSwipe<HTMLDivElement>(
    () => setIndex((i) => (i + 1 < STOPS.length ? i + 1 : i)),
    () => setIndex((i) => Math.max(0, i - 1)),
    open,
  );

  const stop = STOPS[index];
  // A stop whose gesture this device cannot offer is a stop to be read.
  const gesture = stop.askCoarse && !finePointer ? undefined : stop.done;
  const asked = stop.askCoarse && !finePointer ? stop.askCoarse : stop.ask;

  // Reset the tick when the stop changes, or a stop arrives already satisfied.
  useEffect(() => {
    setDid(false);
  }, [index]);

  useEffect(() => {
    if (!open || !gesture) return;
    const off = onSignal((name) => {
      if (name !== gesture) return;
      setDid(true);
      // A beat to read the confirmation, then move on. Long enough to register,
      // short enough that nobody waits for it.
      window.setTimeout(() => {
        setIndex((i) => (i + 1 < STOPS.length ? i + 1 : i));
      }, 1150);
    });
    return off;
  }, [open, gesture, index]);

  const measure = useCallback(() => {
    const node = document.querySelector<HTMLElement>(`[data-tour="${stop.target}"]`);
    if (!node) {
      setRect(null);
      return;
    }
    const box = node.getBoundingClientRect();
    setRect({ top: box.top, left: box.left, width: box.width, height: box.height });
  }, [stop.target]);

  // Bring the step's subject into view before measuring it, or the spotlight
  // lands on something the reader cannot see.
  useEffect(() => {
    if (!open) return;
    const node = document.querySelector<HTMLElement>(`[data-tour="${stop.target}"]`);
    node?.scrollIntoView({ block: "center", behavior: "smooth" });
    const settle = window.setTimeout(measure, 420);
    return () => window.clearTimeout(settle);
  }, [open, stop.target, measure]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open, measure]);

  const finish = useCallback(() => {
    try {
      window.localStorage.setItem(KEY, "done");
    } catch {
      // A browser refusing storage is not a reason to trap somebody in a tour.
    }
    setIndex(0);
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") finish();
      if (event.key === "ArrowRight")
        setIndex((i) => (i + 1 < STOPS.length ? i + 1 : i));
      if (event.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, finish]);

  if (!open) return null;

  const pad = 10;
  const card = cardPosition(rect, stop.side);

  return (
    <div
      ref={swipe}
      // Pointer events pass straight through: the whole point is that the
      // reader reaches the instrument underneath. Only the card takes input.
      className="pointer-events-none fixed inset-0 z-[60]"
      role="dialog"
      aria-label="Console tour"
    >
      {/* The spotlight. One element, and the dimming is its shadow — which is
          how you get a hole in an overlay without clip-path arithmetic. */}
      {rect ? (
        <div
          className="pointer-events-none absolute rounded-[22px] transition-all duration-500"
          style={{
            top: rect.top - pad,
            left: rect.left - pad,
            width: rect.width + pad * 2,
            height: rect.height + pad * 2,
            boxShadow:
              "0 0 0 9999px color-mix(in oklab, var(--void-deep) 74%, transparent), inset 0 0 0 1px color-mix(in oklab, var(--accent) 50%, transparent), 0 0 60px -10px color-mix(in oklab, var(--accent) 50%, transparent)",
          }}
        />
      ) : (
        <div className="absolute inset-0" style={{ background: "color-mix(in oklab, var(--void-deep) 74%, transparent)" }} />
      )}

      <div
        className="glass rise pointer-events-auto absolute w-[min(360px,calc(100vw-2rem))] p-5"
        style={{ ...card, borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <Label>
              Step {index + 1} of {STOPS.length}
            </Label>
            <h2 className="display mt-2 text-[21px] text-[var(--ink)]">{stop.title}</h2>
          </div>
          <button
            onClick={finish}
            aria-label="Skip the tour"
            className="glass-3 glass-interactive shrink-0 rounded-full p-1.5 text-[var(--ink-2)] hover:text-[var(--ink)]"
          >
            <X size={14} />
          </button>
        </div>

        <p className="mt-3 text-[14px] leading-relaxed text-[var(--ink)]">{asked}</p>

        {gesture ? (
          <p
            className="mt-3 flex items-center gap-2 text-[12px] leading-snug transition-colors duration-300"
            style={{ color: did ? "var(--ok)" : "var(--ink-3)" }}
          >
            {did ? (
              <>
                <Check size={13} className="shrink-0" />
                {stop.got}
              </>
            ) : (
              "Go ahead — this waits for you."
            )}
          </p>
        ) : (
          <p className="mt-3 text-[12px] text-[var(--ink-3)]">Esc to skip</p>
        )}

        <div className="mt-5 flex items-center gap-2">
          <div className="flex flex-1 gap-1.5" aria-hidden>
            {STOPS.map((s, i) => (
              <span
                key={s.target}
                className="h-[3px] flex-1 rounded-full transition-colors duration-300"
                style={{
                  background: i <= index ? "var(--accent)" : "rgba(255,255,255,0.14)",
                  boxShadow: i <= index ? "0 0 8px -1px var(--accent)" : undefined,
                }}
              />
            ))}
          </div>
          {index > 0 ? (
            <button
              onClick={() => setIndex((i) => Math.max(0, i - 1))}
              className="glass-3 glass-interactive rounded-full p-2 text-[var(--ink-2)] hover:text-[var(--ink)]"
              aria-label="Previous step"
            >
              <ArrowLeft size={14} />
            </button>
          ) : null}
          {index + 1 < STOPS.length ? (
            <button
              onClick={() => setIndex((i) => i + 1)}
              className="glass-interactive flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-medium"
              style={{
                color: "var(--accent)",
                background: "color-mix(in oklab, var(--accent) 18%, transparent)",
                boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--accent) 45%, transparent)",
              }}
            >
              {gesture && !did ? "Skip this" : "Next"}
              <ArrowRight size={14} />
            </button>
          ) : (
            <button
              onClick={finish}
              className="glass-interactive rounded-full px-4 py-2 text-[13px] font-medium"
              style={{
                color: "var(--ok)",
                background: "color-mix(in oklab, var(--ok) 18%, transparent)",
                boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--ok) 45%, transparent)",
              }}
            >
              Start using it
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Put the card beside its subject, and inside the viewport.
 *
 * The preferred side is a preference: on a narrow screen every side is the
 * wrong one, so it falls back to pinning the card to the bottom of the screen
 * where it can never cover the thing it is describing off-screen.
 */
function cardPosition(rect: Rect | null, side: Stop["side"]) {
  const cardW = Math.min(360, window.innerWidth - 32);
  const gap = 18;

  if (!rect || window.innerWidth < 900) {
    return { left: (window.innerWidth - cardW) / 2, bottom: 24 } as const;
  }

  const clampTop = (top: number) => Math.max(16, Math.min(window.innerHeight - 300, top));

  if (side === "right" && rect.left + rect.width + gap + cardW < window.innerWidth) {
    return { left: rect.left + rect.width + gap, top: clampTop(rect.top) };
  }
  if (side === "left" && rect.left - gap - cardW > 0) {
    return { left: rect.left - gap - cardW, top: clampTop(rect.top) };
  }
  // Below, or above if there is no room below.
  const below = rect.top + rect.height + gap;
  if (below + 260 < window.innerHeight) {
    return { left: Math.min(rect.left, window.innerWidth - cardW - 16), top: below };
  }
  return {
    left: Math.min(rect.left, window.innerWidth - cardW - 16),
    top: clampTop(rect.top - 260 - gap),
  };
}

/** Has this browser seen the tour? Read once, on mount, by the console. */
export function tourSeen() {
  try {
    return window.localStorage.getItem(KEY) === "done";
  } catch {
    return true;
  }
}
