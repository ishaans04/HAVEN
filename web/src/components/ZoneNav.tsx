"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { useMotionOK } from "@/lib/motion";

/**
 * Where you are, and how to get somewhere else.
 *
 * The console is four screens of scroll on a laptop and twice that with the
 * detail open, and until now the only way through it was the wheel. This is the
 * cheapest possible fix: five anchors that say what the page contains, mark
 * which part you are looking at, and jump.
 *
 * It is navigation chrome rather than a set of choices, so it is drawn as
 * quietly as it can be and still be usable — no buttons, no boxes, a hairline
 * under the active one. The masthead spent twelve controls on choices and got
 * cut to three; adding five loud ones back would undo that.
 *
 * Position comes from a scroll listener rather than an IntersectionObserver.
 * The observer reports threshold crossings, which is the wrong shape for "which
 * section am I in" — it goes silent when you jump, and a nav that lies about
 * where you are is worse than no nav.
 */

export interface Zone {
  id: string;
  label: string;
  /**
   * Only a distinct destination while the layout is stacked.
   *
   * Above md the dial and the verdict sit side by side in one grid row, so they
   * share a y-position: "Window" would scroll to exactly where "Recommendation"
   * scrolls, and the position marker could never land on it. Two anchors
   * pointing at one place is a nav that lies about having five stops.
   */
  stackedOnly?: boolean;
}

export const ZONES: Zone[] = [
  { id: "zone-crew", label: "Crew" },
  { id: "zone-window", label: "Window", stackedOnly: true },
  { id: "zone-verdict", label: "Recommendation" },
  { id: "zone-reasoning", label: "How it decided" },
  { id: "zone-audit", label: "Audit" },
];

export function ZoneNav() {
  const [active, setActive] = useState(ZONES[0].id);
  const motionOK = useMotionOK();

  useEffect(() => {
    let frame = 0;

    const measure = () => {
      frame = 0;
      // The line the reader is actually reading at: just under the masthead.
      const masthead =
        parseInt(
          getComputedStyle(document.documentElement).getPropertyValue("--masthead-h"),
          10,
        ) || 150;
      const line = masthead + 90;

      const stacked = window.matchMedia("(max-width: 767px)").matches;
      let current = ZONES[0].id;
      for (const zone of ZONES) {
        if (zone.stackedOnly && !stacked) continue;
        const node = document.getElementById(zone.id);
        if (!node) continue;
        if (node.getBoundingClientRect().top <= line) current = zone.id;
      }
      // At the very bottom the last zone may never reach the line, and a nav
      // that cannot mark the section you are standing in is broken.
      const atBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 8;
      if (atBottom) current = ZONES[ZONES.length - 1].id;

      setActive(current);
    };

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  const go = (id: string) => {
    const node = document.getElementById(id);
    if (!node) return;
    const masthead =
      parseInt(
        getComputedStyle(document.documentElement).getPropertyValue("--masthead-h"),
        10,
      ) || 150;
    const top = node.getBoundingClientRect().top + window.scrollY - masthead - 16;
    window.scrollTo({ top, behavior: motionOK ? "smooth" : "auto" });
  };

  return (
    <nav aria-label="Console sections" className="fade-x no-bar -mb-px overflow-x-auto">
      <ul className="flex min-w-max gap-5">
        {ZONES.map((zone) => {
          const on = zone.id === active;
          return (
            <li key={zone.id} className={zone.stackedOnly ? "md:hidden" : undefined}>
              <button
                onClick={() => go(zone.id)}
                aria-current={on ? "true" : undefined}
                className={clsx(
                  "relative whitespace-nowrap pb-2.5 pt-1 text-[11px] font-medium uppercase tracking-[0.12em] transition-colors",
                  on ? "text-[var(--iris)]" : "text-[var(--ink-3)] hover:text-[var(--ink-2)]",
                )}
              >
                {zone.label}
                <span
                  aria-hidden
                  className="absolute inset-x-0 bottom-0 h-[2px] rounded-full transition-opacity duration-300"
                  style={{
                    background: "var(--iris)",
                    boxShadow: "0 0 8px -1px var(--iris)",
                    opacity: on ? 1 : 0,
                  }}
                />
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
