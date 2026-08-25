"use client";

import { useEffect, useRef } from "react";
import { useMotionOK } from "@/lib/motion";

/**
 * The starfield behind everything.
 *
 * Generated rather than shipped: a seeded PRNG lays out the field at module
 * load, so it is identical on every render and in every build, weighs nothing,
 * and needs no image pipeline behind a static export.
 *
 * ## Three depths, and why it moves
 *
 * It used to be two static layers in one SVG, pinned to the viewport. Two
 * layers at different scales do read as distance, but nothing about a field
 * that never moves reads as *space* — the sky was the only part of these pages
 * with no life in it at all, on a product whose subject is being in orbit.
 *
 * Depth comes from three things acting together, which is roughly how the eye
 * gets it from a real sky:
 *
 *   · **size and brightness** — near stars are larger and hotter
 *   · **drift** — each layer wanders on its own period and amplitude, the near
 *     field visibly further per cycle than the far one
 *   · **scroll parallax** — the near field slides against the page four times
 *     faster than the far one, which is the cue that actually sells it
 *
 * ## Two decisions worth keeping
 *
 * **The drift is CSS, not rAF.** §8: requestAnimationFrame is throttled to a
 * fraction of a hertz in a backgrounded tab and suspended outright in a hidden
 * one. This runs behind every screen of both pages, and a sky that freezes the
 * moment a tab loses focus is worse than one that never moved. CSS keyframes
 * run off their own timeline and are not throttled. The keyframe returns to
 * its start at 100%, so it loops seamlessly without the field having to tile.
 *
 * **Scroll parallax is a transform on a wrapper, and the drift is on a child.**
 * One element cannot carry two transforms from two sources; nesting them lets
 * the compositor keep both without either fighting the other.
 */

// Mulberry32. Small, fast, and deterministic — the only property that matters
// here is that the sky does not change between two builds of the same commit.
function prng(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Star {
  x: number;
  y: number;
  r: number;
  o: number;
  /** Seconds of delay, for the few that are allowed to scintillate. */
  t: number;
}

function field(seed: number, count: number, rMin: number, rMax: number, oMin: number, oMax: number) {
  const random = prng(seed);
  const stars: Star[] = [];
  for (let i = 0; i < count; i += 1) {
    stars.push({
      x: Math.round(random() * 10000) / 10,
      y: Math.round(random() * 10000) / 10,
      r: Math.round((rMin + random() * (rMax - rMin)) * 100) / 100,
      o: Math.round((oMin + random() * (oMax - oMin)) * 100) / 100,
      t: Math.round(random() * 900) / 100,
    });
  }
  return stars;
}

interface Layer {
  stars: Star[];
  fill: string;
  /** Pixels of page scroll translated into pixels of star travel. */
  rate: number;
  /** Drift amplitude, in viewBox units, and its period in seconds. */
  dx: number;
  dy: number;
  period: number;
  /** Every nth star scintillates. Higher is rarer. */
  sparkle: number;
}

/**
 * Far to near. The counts fall and the sizes rise together, because a sky with
 * as many bright stars as dim ones reads as noise rather than as distance.
 */
const LAYERS: Layer[] = [
  {
    stars: field(20260822, 190, 0.28, 0.55, 0.1, 0.34),
    fill: "#ffffff",
    rate: 0.012,
    dx: -9,
    dy: 5,
    period: 260,
    sparkle: 0,
  },
  {
    stars: field(19680067, 84, 0.5, 0.85, 0.28, 0.58),
    fill: "var(--star)",
    rate: 0.028,
    dx: 14,
    dy: -8,
    period: 185,
    sparkle: 11,
  },
  {
    stars: field(31415926, 34, 0.8, 1.45, 0.55, 0.95),
    fill: "var(--star)",
    rate: 0.052,
    dx: -22,
    dy: 13,
    period: 130,
    sparkle: 5,
  },
];

export function StarField() {
  const host = useRef<HTMLDivElement>(null);
  const motionOK = useMotionOK();

  /**
   * Scroll parallax, written straight to the DOM.
   *
   * Deliberately not React state: this fires on every scroll frame, and a
   * `setState` per frame would re-render three hundred circles to move a
   * wrapper. The layers are read back out of the DOM instead and their
   * transforms set directly, which is one style write each.
   */
  useEffect(() => {
    const node = host.current;
    if (!node || !motionOK) return;

    const layers = Array.from(node.querySelectorAll<HTMLElement>("[data-rate]"));
    let frame = 0;

    const apply = () => {
      frame = 0;
      const y = window.scrollY;
      for (const el of layers) {
        const rate = Number(el.dataset.rate) || 0;
        // Negative: the sky lags the page, which is what makes it sit behind.
        el.style.transform = `translate3d(0, ${(-y * rate).toFixed(2)}px, 0)`;
      }
    };

    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(apply);
    };

    apply();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [motionOK]);

  return (
    <div ref={host} aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {LAYERS.map((layer, li) => (
        // Outer: scroll parallax. Inner: drift. One transform each.
        <div
          key={li}
          data-rate={layer.rate}
          className="absolute inset-0 will-change-transform"
        >
          <div
            className="absolute inset-0"
            style={
              motionOK
                ? ({
                    "--drift-x": `${layer.dx}px`,
                    "--drift-y": `${layer.dy}px`,
                    animation: `star-drift ${layer.period}s ease-in-out infinite`,
                  } as React.CSSProperties)
                : undefined
            }
          >
            <svg
              className="absolute inset-0 h-full w-full"
              viewBox="0 0 1000 1000"
              preserveAspectRatio="xMidYMid slice"
            >
              {layer.stars.map((s, i) => {
                const twinkles = motionOK && layer.sparkle > 0 && i % layer.sparkle === 0;
                return (
                  <circle
                    key={i}
                    cx={s.x}
                    cy={s.y}
                    r={s.r}
                    fill={layer.fill}
                    opacity={s.o}
                    style={
                      twinkles
                        ? ({
                            "--o": s.o,
                            animation: `star-twinkle ${6 + (i % 5)}s ease-in-out ${s.t}s infinite`,
                          } as React.CSSProperties)
                        : undefined
                    }
                  />
                );
              })}
            </svg>
          </div>
        </div>
      ))}
    </div>
  );
}
