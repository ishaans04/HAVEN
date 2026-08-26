"use client";

import { useEffect, useRef } from "react";
import { Earth } from "./Earth";
import { StarField } from "./StarField";
import { useMotionOK } from "@/lib/motion";

/**
 * The setting.
 *
 * The console used to hold its space imagery inside a card, which is a strange
 * thing to do with a planet. Here the scene is the room the consultation happens
 * in: stars behind everything, Earth's limb along the bottom edge, and a slow
 * terminator glow that drifts the way a real one would at 7.66 km/s.
 *
 * It carries one piece of state and no more. The ember low on the horizon takes
 * its hue from the answer, so a refusal visibly cools the room without a single
 * word changing. Everything else is deliberately inert — a background that
 * competes with the text has stopped being a background.
 *
 * Motion is opt-out at the OS level and the whole thing is `aria-hidden`; a
 * screen reader gets nothing here, because there is nothing here to get.
 */
export function Scene({ tone }: { tone: "ok" | "warn" | "bad" }) {
  const ember = useRef<HTMLDivElement>(null);
  const motionOK = useMotionOK();

  // A very slight parallax on the limb. Two per cent of the scroll distance:
  // enough that the horizon feels further away than the text, not enough to
  // read as an effect.
  const limb = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!motionOK) return;
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (limb.current) {
          limb.current.style.transform = `translate3d(0, ${window.scrollY * 0.02}px, 0)`;
        }
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [motionOK]);

  const hue =
    tone === "bad" ? "var(--crit)" : tone === "warn" ? "var(--accent)" : "var(--atmo)";

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <StarField />

      {/* The ember on the horizon, tinted by the verdict. */}
      <div
        ref={ember}
        className="scene-ember absolute inset-x-0 bottom-0 h-[46vh]"
        style={{
          background: `radial-gradient(64% 100% at 50% 100%, color-mix(in oklab, ${hue} 22%, transparent), transparent 70%)`,
        }}
      />

      {/* Earth, along the bottom. The same rendered sphere the landing uses,
          pushed far enough below the fold that only the limb is in frame — so
          the console gets a real horizon with a real terminator crossing it
          rather than a curve drawn to look like one. The orbit track is off:
          the console draws its own 24-hour window as a dial, and two orbits on
          one screen would be two different clocks. */}
      <div
        ref={limb}
        className="absolute inset-0 will-change-transform"
        style={{
          maskImage: "linear-gradient(to top, #000 34%, transparent 92%)",
          WebkitMaskImage: "linear-gradient(to top, #000 34%, transparent 92%)",
        }}
      >
        {/* A shallow limb across the bottom quarter — the curve you get looking
            at Earth from low orbit, not the tight ball you get from further
            out. Dimmed hard: on the landing the planet is the subject, here it
            is the room, and a lit limb at full strength competes with every
            readout on the page. */}
        <Earth
          className="absolute inset-0 opacity-[0.45]"
          placement={{ cx: 0.5, r: 1.15, topAt: 0.74 }}
          orbit={false}
        />
      </div>
    </div>
  );
}
