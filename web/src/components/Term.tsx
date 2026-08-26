"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * A word this console cannot avoid, with its meaning one hover away.
 *
 * The vocabulary here is not decoration — "precondition", "admissible" and
 * "deterministic" each carry a distinction the product depends on, and
 * paraphrasing them away would cost the precision that makes the claims worth
 * anything. But a reader meeting the console for the first time does not have
 * that vocabulary, and a sentence built from four words they do not know is a
 * sentence they skip.
 *
 * So the term stays and the meaning arrives on demand. Sighted readers get a
 * dotted underline and a tooltip on hover or focus; screen readers get the
 * definition inline, always, because a definition behind a hover is no
 * definition at all to somebody not using a pointer.
 *
 * The tooltip renders through a portal. Several of the cards it appears inside
 * set `overflow: hidden` to clip their own corners, and a tooltip drawn as a
 * child would be clipped with them.
 */

export const GLOSSARY: Record<string, string> = {
  passage: "One numbered chunk of a procedure document — a single rule, with its own text and its own conditions.",
  preconditions:
    "The conditions a rule states before it applies: what kind of task, whose alertness, how critical. All of them must hold.",
  precondition:
    "A condition a rule states before it applies: what kind of task, whose alertness, how critical.",
  deterministic:
    "Ordinary arithmetic. The same inputs give the same answer every time, and no model is involved.",
  admissible: "Allowed to be used — the rule's own conditions all hold for this situation.",
  checker:
    "The deterministic step that tests a rule's conditions against the situation. The AI proposes; this disposes.",
  corpus: "The set of procedure documents HAVEN is allowed to read and cite.",
  "retrieval score":
    "How closely a rule's wording matches the situation. It decides what gets shortlisted, and nothing after that.",
  "hash-chained":
    "Each logged step is sealed to the one before it, so altering any entry stops the chain verifying.",
  "Three-Process Model":
    "A published model of alertness built from sleep history, hours awake and body-clock phase.",
  "NASA-TLX": "A standard aerospace measure of how much work a person is handling at once.",
  circadian: "The body's roughly 24-hour clock, which creates a natural alertness low in the small hours.",
  escalate: "Hand the decision to a named human rather than answering it.",
};

export function Term({ k, children }: { k: keyof typeof GLOSSARY | string; children?: React.ReactNode }) {
  const definition = GLOSSARY[k];
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState<{ top: number; left: number } | null>(null);
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    // Follow the term rather than dismiss. Moving focus to a term scrolls it
    // into view, and a tooltip that closes on scroll closes itself the instant
    // a keyboard reaches it.
    const track = () => {
      const rect = ref.current?.getBoundingClientRect();
      if (rect) setBox({ top: rect.top, left: rect.left + rect.width / 2 });
    };
    window.addEventListener("scroll", track, true);
    window.addEventListener("resize", track);
    return () => {
      window.removeEventListener("scroll", track, true);
      window.removeEventListener("resize", track);
    };
  }, [open]);

  if (!definition) return <>{children ?? k}</>;

  const show = () => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    setBox({ top: rect.top, left: rect.left + rect.width / 2 });
    setOpen(true);
  };

  return (
    <button
      ref={ref}
      type="button"
      onMouseEnter={show}
      onMouseLeave={() => setOpen(false)}
      onFocus={show}
      onBlur={() => setOpen(false)}
      onClick={(event) => {
        // Touch has no hover. A tap is the only way in on a phone.
        event.preventDefault();
        if (open) setOpen(false);
        else show();
      }}
      className="term"
    >
      {children ?? k}
      {/* Always in the DOM, so the meaning does not depend on owning a mouse. */}
      <span className="sr-only"> ({definition})</span>

      {open && box
        ? createPortal(
            <span
              role="tooltip"
              className="pointer-events-none fixed z-[70] block w-[min(280px,calc(100vw-2rem))]"
              style={{
                top: box.top > 150 ? box.top - 10 : box.top + 26,
                left: Math.min(Math.max(box.left, 150), window.innerWidth - 150),
                transform: `translate(-50%, ${box.top > 150 ? "-100%" : "0"})`,
              }}
            >
              <span
                className="glass block p-3 text-left"
                style={{ borderRadius: "var(--radius-sm)" }}
              >
                <span className="block text-[12px] font-normal leading-relaxed text-[var(--ink-2)]">
                  {definition}
                </span>
              </span>
            </span>,
            document.body,
          )
        : null}
    </button>
  );
}
