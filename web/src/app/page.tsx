import type { Metadata } from "next";
import { Landing } from "@/components/Landing";

/**
 * `/` — the landing page.
 *
 * A server component whose only job is metadata, wrapping a client component
 * that does the rendering. The console lives at `/console/`; putting it behind
 * one deliberate click is the point of having this page at all.
 *
 * `scripts/smoke` asserts that `/` returns HTML, which it still does. FastAPI
 * mounts the export with `html=True`, so `/console/` resolves to
 * `console/index.html` without any routing change on the API side.
 */
export const metadata: Metadata = {
  title: "HAVEN — Fatigue-Aware Safety Co-Pilot",
  description:
    "A tired operator and an irreversible task are about to meet. HAVEN sees the collision coming, finds the procedure that governs it, and hands a human the decision — or refuses to guess.",
};

export default function Page() {
  return <Landing />;
}
