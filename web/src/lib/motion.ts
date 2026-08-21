"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Motion primitives.
 *
 * Three rules hold everywhere below.
 *
 * **Reduced motion is a hard gate, not a dimmer.** Every hook here returns
 * inert values when the user has asked for less motion — no parallax, no
 * tilt, no reveal. The layout must be correct with all of it switched off,
 * which is also what makes it correct before hydration.
 *
 * **Nothing reads layout in an event handler.** Pointer and scroll handlers
 * only stash numbers; a single rAF pass writes them to CSS custom properties.
 * Reading `getBoundingClientRect` inside a `scroll` listener is how a smooth
 * page becomes a janky one.
 *
 * **Everything animates transform or opacity.** Those are the two properties
 * the compositor can handle without touching layout or paint. A parallax built
 * on `top` looks identical for one frame and terrible for the rest.
 */

const REDUCED = "(prefers-reduced-motion: reduce)";
const FINE = "(hover: hover) and (pointer: fine)";

function useMediaQuery(query: string, fallback: boolean) {
  const [matches, setMatches] = useState(fallback);

  useEffect(() => {
    const mq = window.matchMedia(query);
    setMatches(mq.matches);
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/** True when the reader has not asked for reduced motion. */
export function useMotionOK() {
  // Assume motion is wanted until measured, and *not* the reverse. Defaulting
  // to reduced looks safer and is not: every consumer below then resolves to
  // its finished state on the first effect pass, which for `useReveal` means
  // the observer never attaches and the page arrives pre-revealed. A reader who
  // does want reduced motion loses one frame instead, and sees no animation.
  return !useMediaQuery(REDUCED, false);
}

/** True for a mouse or trackpad. Touch gets gestures instead of hover effects. */
export function useFinePointer() {
  return useMediaQuery(FINE, false);
}

/* --------------------------------------------------------------------------
   Reveal
   --------------------------------------------------------------------------
   One shared watcher for every element waiting to be revealed, rather than an
   IntersectionObserver each.

   The obvious implementation is an observer per element, and it has a failure
   mode that matters: an observer only reports *threshold crossings*, so an
   instantaneous jump past an element — an anchor link, a restored scroll
   position, Cmd+End — takes it from "below the fold, not intersecting" to
   "above the fold, not intersecting" without ever being sampled in between. No
   callback fires, and the element stays hidden for the rest of the session.
   Content that can be permanently invisible is not an acceptable trade for an
   animation.

   So: position is compared directly, once per animation frame in which a
   scroll happened, across every pending element at once. Each one is dropped
   from the set the moment it fires, the listeners detach when the set empties,
   and passing something without ever rendering it is not expressible.
   -------------------------------------------------------------------------- */

interface Watcher {
  node: HTMLElement;
  fire: () => void;
}

const watchers = new Set<Watcher>();
let scheduled = 0;
let listening = false;

function flush() {
  scheduled = 0;
  const limit = window.innerHeight * 0.88;
  // A copy, because firing removes entries from the set being walked.
  for (const watcher of Array.from(watchers)) {
    if (watcher.node.getBoundingClientRect().top < limit) {
      watchers.delete(watcher);
      watcher.fire();
    }
  }
  if (!watchers.size) detach();
}

function schedule() {
  if (!scheduled) scheduled = requestAnimationFrame(flush);
}

function attach() {
  if (listening) return;
  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule, { passive: true });
  listening = true;
}

function detach() {
  if (!listening) return;
  window.removeEventListener("scroll", schedule);
  window.removeEventListener("resize", schedule);
  listening = false;
}

/** Reveal an element once it reaches the lower part of the viewport. */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [shown, setShown] = useState(false);
  const motionOK = useMotionOK();

  useEffect(() => {
    if (!motionOK) {
      setShown(true);
      return;
    }
    const node = ref.current;
    if (!node) return;

    const watcher: Watcher = { node, fire: () => setShown(true) };
    watchers.add(watcher);
    attach();
    // Anything already on screen at mount — the hero, a short page — resolves
    // on this first pass rather than waiting for a scroll that may never come.
    schedule();

    return () => {
      watchers.delete(watcher);
      if (!watchers.size) detach();
    };
  }, [motionOK]);

  return { ref, shown };
}

interface ParallaxTargets {
  /** How far this layer travels per pixel of scroll. Negative moves it up. */
  scroll?: number;
  /** How far this layer travels across the full width of pointer travel, in px. */
  pointer?: number;
}

/**
 * Scroll- and pointer-linked parallax for a set of layers inside one section.
 *
 * Returns a ref for the section and a `layer` factory that produces the props
 * for each moving child. One listener pair and one rAF for the whole section,
 * however many layers it drives — which is the difference between parallax
 * that costs nothing and parallax that costs a frame per layer.
 */
export function useParallax<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const layers = useRef<{ node: HTMLElement; scroll: number; pointer: number }[]>([]);
  const motionOK = useMotionOK();
  const fine = useFinePointer();

  useEffect(() => {
    const section = ref.current;
    if (!section || !motionOK) return;

    // Captured once: the array identity is stable for the component's life, and
    // reading `.current` in cleanup would read whatever it points at then.
    const registered = layers.current;
    let scrollY = 0;
    let px = 0;
    let py = 0;
    let frame = 0;

    const write = () => {
      frame = 0;
      for (const layer of registered) {
        const y = scrollY * layer.scroll + py * layer.pointer * 0.5;
        const x = px * layer.pointer;
        layer.node.style.transform = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0)`;
      }
    };

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(write);
    };

    const onScroll = () => {
      // Only the section's own offset matters; once it is off screen the
      // layers are not visible and their transform is irrelevant.
      scrollY = Math.max(0, Math.min(window.scrollY, section.offsetHeight));
      schedule();
    };

    const onPointer = (event: PointerEvent) => {
      const box = section.getBoundingClientRect();
      px = (event.clientX - box.left) / box.width - 0.5;
      py = (event.clientY - box.top) / box.height - 0.5;
      schedule();
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    if (fine) section.addEventListener("pointermove", onPointer);

    return () => {
      window.removeEventListener("scroll", onScroll);
      section.removeEventListener("pointermove", onPointer);
      if (frame) cancelAnimationFrame(frame);
      for (const layer of registered) layer.node.style.transform = "";
    };
  }, [motionOK, fine]);

  const layer = ({ scroll = 0, pointer = 0 }: ParallaxTargets) => ({
    ref: (node: HTMLElement | null) => {
      if (!node) return;
      const existing = layers.current.find((l) => l.node === node);
      if (existing) {
        existing.scroll = scroll;
        existing.pointer = pointer;
      } else {
        layers.current.push({ node, scroll, pointer });
      }
    },
  });

  return { ref, layer };
}

/**
 * Pointer tilt.
 *
 * A few degrees of rotation toward the cursor, on a container that has
 * perspective. Deliberately small: this is an instrument, and an instrument
 * that swings when you move the mouse reads as a toy. Four degrees is enough
 * for the reader to feel that the surface has a normal.
 */
export function useTilt<T extends HTMLElement>(maxDeg = 4) {
  const ref = useRef<T>(null);
  const motionOK = useMotionOK();
  const fine = useFinePointer();

  useEffect(() => {
    const node = ref.current;
    if (!node || !motionOK || !fine) return;

    let frame = 0;
    let rx = 0;
    let ry = 0;

    const write = () => {
      frame = 0;
      node.style.setProperty("--tilt-x", `${rx.toFixed(2)}deg`);
      node.style.setProperty("--tilt-y", `${ry.toFixed(2)}deg`);
    };

    const onMove = (event: PointerEvent) => {
      const box = node.getBoundingClientRect();
      const dx = (event.clientX - box.left) / box.width - 0.5;
      const dy = (event.clientY - box.top) / box.height - 0.5;
      ry = dx * maxDeg * 2;
      rx = -dy * maxDeg * 2;
      if (!frame) frame = requestAnimationFrame(write);
    };

    const onLeave = () => {
      rx = 0;
      ry = 0;
      if (!frame) frame = requestAnimationFrame(write);
    };

    node.addEventListener("pointermove", onMove);
    node.addEventListener("pointerleave", onLeave);
    return () => {
      node.removeEventListener("pointermove", onMove);
      node.removeEventListener("pointerleave", onLeave);
      if (frame) cancelAnimationFrame(frame);
      node.style.removeProperty("--tilt-x");
      node.style.removeProperty("--tilt-y");
    };
  }, [motionOK, fine, maxDeg]);

  return ref;
}

/**
 * Horizontal swipe.
 *
 * Touch's equivalent of the arrow keys the tour already answers to. Threshold
 * and axis-dominance check are there so a scroll down a page that happens to
 * drift sideways does not count as a swipe.
 */
export function useSwipe<T extends HTMLElement>(
  onLeft: () => void,
  onRight: () => void,
  enabled = true,
  threshold = 56,
) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || !enabled) return;

    let startX = 0;
    let startY = 0;
    let tracking = false;

    const onStart = (event: TouchEvent) => {
      const touch = event.touches[0];
      startX = touch.clientX;
      startY = touch.clientY;
      tracking = true;
    };

    const onEnd = (event: TouchEvent) => {
      if (!tracking) return;
      tracking = false;
      const touch = event.changedTouches[0];
      const dx = touch.clientX - startX;
      const dy = touch.clientY - startY;
      if (Math.abs(dx) < threshold || Math.abs(dx) < Math.abs(dy) * 1.4) return;
      if (dx < 0) onLeft();
      else onRight();
    };

    node.addEventListener("touchstart", onStart, { passive: true });
    node.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      node.removeEventListener("touchstart", onStart);
      node.removeEventListener("touchend", onEnd);
    };
  }, [onLeft, onRight, enabled, threshold]);

  return ref;
}
