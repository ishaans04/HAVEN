"use client";

import { useEffect, useRef } from "react";
import { PlanetLimb } from "./PlanetLimb";
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

      {/* Earth, along the bottom. Bled off both edges so it reads as a limb
          rather than as an illustration sitting in the layout. */}
      <div
        ref={limb}
        className="absolute inset-x-[-6%] bottom-[-8vh] h-[58vh] will-change-transform"
        style={{
          maskImage: "linear-gradient(to top, #000 42%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to top, #000 42%, transparent 100%)",
        }}
      >
        <PlanetLimb className="h-full w-full" />
      </div>
    </div>
  );
}
