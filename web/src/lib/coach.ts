"use client";

/**
 * A one-way channel from "the reader did something" to "the tour noticed".
 *
 * The first-run tour used to be four paragraphs describing instruments that
 * were sitting right there — 181 words asking somebody to read about a dial
 * instead of turning it. Replacing that with four things to *do* needs the
 * tour to know when each one has been done, and the obvious way to arrange
 * that — threading `onDidScrub` style callbacks down through Console into
 * OrbitDial and CrewRail — would make three components that have nothing to do
 * with onboarding carry props about it.
 *
 * So the components announce, and whoever cares listens. Nothing listens
 * unless the tour is open, which makes `signal` a set iteration over an empty
 * set the rest of the time.
 *
 * Deliberately not a DOM CustomEvent: this is typed, it cannot collide with
 * anything else on `window`, and it does not survive a page teardown.
 */

/** The four things the tour asks for, and nothing else. */
export type Signal =
  /** A crew member was chosen from the rail. */
  | "crew"
  /** The dial was swept to an hour reading below the execution threshold. */
  | "trough"
  /** The flagged task was moved to an hour where it clears that threshold. */
  | "cleared"
  /** Evidence was unfolded — any disclosure opened. */
  | "evidence";

const listeners = new Set<(signal: Signal) => void>();

export function signal(name: Signal) {
  // Copied before iterating: a listener that unsubscribes itself on the
  // signal it was waiting for — which is exactly what the tour does — would
  // otherwise mutate the set mid-iteration.
  Array.from(listeners).forEach((fn) => fn(name));
}

export function onSignal(fn: (signal: Signal) => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}
