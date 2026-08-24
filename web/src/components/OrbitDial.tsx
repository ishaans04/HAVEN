"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { CrewReadiness, TimelineTask } from "@/lib/types";
import { useFinePointer, useMotionOK } from "@/lib/motion";
import { useElementWidth } from "@/lib/useElementWidth";
import { signal } from "@/lib/coach";
import { Earth } from "./Earth";
import { TONE_VAR, hoursSince, toneOf, utcTime } from "./ui";

/**
 * The orbit dial — Zone 2, as a dial rather than a chart.
 *
 * v1 plotted predicted alertness as a line chart with the day on the x-axis.
 * That is the correct instrument for someone reading values, and the wrong one
 * for someone asking "is a hard task about to land in a bad hour?" — because on
 * a line chart the answer is a coordinate lookup, and a day is not a line. It
 * is a cycle, and the reader already owns a mental model for reading one: a
 * clock face.
 *
 * So: twenty-four hours around the ring, midnight at the top. The band is
 * predicted alertness, drawn at a radius set by the score, which makes the
 * shape of the whole day legible before any number is read — a dip toward the
 * centre is the circadian trough, and you can see it without being told.
 *
 * Every task sits at its scheduled hour, at the radius of the curve at that
 * moment. That placement is the entire argument of the product in one mark: a
 * task low on the dial is a hard job landing in a bad hour. Nothing about it is
 * decorative — move a task an hour and the mark moves with it.
 *
 * The linear chart still exists, in the details drawer, for reading values off.
 *
 * ## Why it is now a ring in space rather than a flat face
 *
 * The centre used to hold a planet built out of two radial gradients and eight
 * hard-coded ellipses scrolling sideways under a clip path. It was the same
 * fake the landing page threw out — a shape that knew nothing about where the
 * sun was — and it sat at the middle of the one view judges actually spend
 * their time in. It is gone. `Earth` renders the real sphere here, the same one
 * the landing uses, with its own orbit track switched off: `Scene` already
 * settled that two orbits on one screen would be two different clocks, and the
 * dial *is* this screen's orbit.
 *
 * A real sphere makes a flat ring around it look painted on, so the ring is
 * projected too. It is a genuine circle in 3-space, inclined, sampled and
 * drawn through one projection.
 *
 * ## Three rules the projection obeys
 *
 * **Orthographic, never perspective.** Radius carries the alertness score, so
 * anything that scales radius with depth is lying about data — a near-side
 * reading would plot higher than a far-side reading of the same value. Depth is
 * therefore allowed to change how a mark is *shaded and sized*, and never where
 * it *is*. At `tilt = 90°` this degenerates exactly to the flat dial that came
 * before it, which is the cheapest possible proof the geometry is sound.
 *
 * **Midnight stays at the top.** Tilt is the only free parameter. Any rotation
 * in the plane of the ring would slide the hours around the face, and an
 * instrument whose 03:00 is somewhere different each time you look is not an
 * instrument. Dragging changes the angle you view the ring from, nothing else.
 *
 * **Geometry occludes; data does not.** The far half of the ring (06–18) is
 * masked where the sphere stands, so it passes genuinely behind the planet
 * rather than over it. Task markers are exempt: a marker hidden behind the
 * globe is a task the reader cannot click, and an unreachable task is a worse
 * failure than a small perspective lie. They dim instead.
 */

const SIZE = 460;
const C = SIZE / 2;

const AURORA_IN = 132;
const AURORA_OUT = 188;
const BAND_R = 198;
const LABEL_R = 214;
const PLANET_R = 102;
const THRESHOLD = 0.7;

/**
 * The sphere's own box, in viewBox units. Wider than the planet because the
 * shader draws atmosphere *outside* the disc and a box cropped to the disc
 * would clip the limb.
 */
const GLOBE_BOX = 340;

const TAU = Math.PI * 2;
const RAD = Math.PI / 180;

/**
 * Face-on — an ordinary flat clock — is 90°. The default leans back far enough
 * to read unmistakably as a ring in space, and not so far that the hours bunch
 * up near the poles of the ellipse.
 *
 * The floor is 40° rather than something more dramatic for a measured reason:
 * the hour labels ride at `LABEL_R`, so their vertical reach is
 * `LABEL_R · sin(tilt)`, and below about 38° that carries the 00 and 12 labels
 * onto the lit sphere, where §8's compositing trap makes contrast a thing you
 * can no longer reason about by reading CSS. At 40° they clear the disc by
 * ~25 units at both poles and stay on the page's own dark ground.
 */
const TILT_DEFAULT = 62 * RAD;
const TILT_MIN = 40 * RAD;
const TILT_MAX = 90 * RAD;

const radiusFor = (score: number) => AURORA_IN + Math.max(0, Math.min(1, score)) * (AURORA_OUT - AURORA_IN);

/** Hour of the window to angle on the ring, midnight at the top. */
const angleFor = (hour: number) => (hour / 24) * TAU - Math.PI / 2;

type Pt = { x: number; y: number; depth: number };

/**
 * A point on the orbital plane, projected.
 *
 * `depth` runs +1 (nearest the reader) to −1 (furthest), and is used only for
 * shading, sizing and draw order. Because `cos(tilt) ≥ 0` across the whole
 * range, its sign depends only on the hour: 06–18 is always the far half and
 * 18–06 always the near one, which is what lets the near/far split be computed
 * once from hour boundaries instead of per frame.
 */
function project(hour: number, radius: number, tilt: number): Pt {
  const a = angleFor(hour);
  return {
    x: C + radius * Math.cos(a),
    y: C + radius * Math.sin(a) * Math.sin(tilt),
    depth: -Math.sin(a) * Math.cos(tilt),
  };
}

/** True for hours on the near half of the ring — the side facing the reader. */
const isNear = (hour: number) => !(hour > 6 && hour < 18);

const polyline = (pts: Pt[]) =>
  pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ");

/** An arc of the ring at a constant radius, as a projected polyline. */
function ringPath(from: number, to: number, radius: number, tilt: number, steps = 72) {
  const pts: Pt[] = [];
  for (let i = 0; i <= steps; i++) {
    pts.push(project(from + ((to - from) * i) / steps, radius, tilt));
  }
  return polyline(pts);
}

/**
 * Split an hour range at the near/far boundaries, so each piece can be handed
 * to the group that draws its own side of the planet.
 */
function halves(from: number, to: number) {
  const cuts = [6, 18].filter((b) => b > from && b < to);
  const out: { from: number; to: number; near: boolean }[] = [];
  let cursor = from;
  for (const edge of [...cuts, to]) {
    out.push({ from: cursor, to: edge, near: isNear((cursor + edge) / 2) });
    cursor = edge;
  }
  return out;
}

/** Contiguous runs of a flag along the curve, as [startHour, endHour]. */
function runs(points: { h: number; flag: boolean }[]): [number, number][] {
  const out: [number, number][] = [];
  let start: number | null = null;
  points.forEach((p, i) => {
    if (p.flag && start === null) start = p.h;
    const ending = !p.flag || i === points.length - 1;
    if (start !== null && ending) {
      if (p.h - start > 0.05) out.push([start, p.h]);
      start = null;
    }
  });
  return out;
}

type Sample = { h: number; score: number; asleep: boolean; low: boolean };

/**
 * The alertness ribbon over one stretch of hours: the curve on the outside,
 * the floor at `AURORA_IN` on the inside, closed.
 */
function ribbonPath(list: Sample[], tilt: number) {
  if (list.length < 2) return "";
  const outer = list.map((s) => project(s.h, radiusFor(s.score), tilt));
  const inner = [...list].reverse().map((s) => project(s.h, AURORA_IN, tilt));
  return `${polyline(outer)} ${polyline(inner).replace(/^M/, "L")} Z`;
}

const between = (list: Sample[], lo: number, hi: number) =>
  list.filter((s) => s.h >= lo && s.h <= hi);

/**
 * The lit edge of the ribbon, drawn on.
 *
 * A path can only draw itself if it knows how long it is, and only the rendered
 * element knows that — so each piece measures itself after commit. It is a
 * component rather than a ref in the parent because the curve is now three
 * pieces (near, far, near) and they each need their own length.
 */
function EdgeArc({ d, animate }: { d: string; animate: boolean }) {
  const ref = useRef<SVGPathElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || !animate) return;
    const length = Math.ceil(node.getTotalLength());
    node.style.setProperty("--draw-length", String(length));
    node.style.strokeDasharray = String(length);
  }, [animate, d]);

  if (!d) return null;
  return (
    <path
      ref={ref}
      d={d}
      fill="none"
      stroke="var(--info)"
      strokeWidth={1.8}
      strokeOpacity={0.92}
      strokeLinejoin="round"
      strokeLinecap="round"
      filter="url(#od-glow)"
      className={animate ? "draw-on" : undefined}
    />
  );
}

export function OrbitDial({
  crew,
  tasks,
  windowStart,
  selectedSituation,
  onSelectSituation,
  loading,
}: {
  crew: CrewReadiness | null;
  tasks: TimelineTask[];
  windowStart: string;
  selectedSituation: string | null;
  onSelectSituation: (situationId: string) => void;
  loading?: boolean;
}) {
  const { ref: box, width } = useElementWidth<HTMLDivElement>();
  const motionOK = useMotionOK();
  const finePointer = useFinePointer();
  const [hovered, setHovered] = useState<string | null>(null);
  const [tilt, setTilt] = useState(TILT_DEFAULT);

  // The dial is drawn in viewBox units and scaled to whatever width it lands
  // in, which would shrink its labels and hit targets along with it. Dividing
  // by that scale gives marks a *constant on-screen* size instead: 11px type
  // and a 34px touch target at 300px wide and at 520px wide alike.
  const k = width > 0 ? SIZE / width : 1;
  const px = (onScreen: number) => onScreen * k;

  /* ---- grab it -----------------------------------------------------------
     Vertical drag lowers the eye toward the orbital plane, the way camera
     elevation works everywhere else, so dragging down flattens the ring
     towards edge-on.

     Fine pointers only. On a touch screen this column scrolls, and a vertical
     drag that tilted the dial instead of moving the page would be a scroll
     trap on the exact viewport §8 records as hard-won. Coarse pointers get the
     default angle and an unbroken page. */
  const drag = useRef({ id: null as number | null, y: 0, moved: false });
  /** Set for one tick after a drag, so the click it raises can be ignored. */
  const dragged = useRef(false);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!finePointer) return;
    drag.current = { id: event.pointerId, y: event.clientY, moved: false };
  };

  /**
   * Where the pointer is on the ring, in hours — or null when it is nowhere
   * near it.
   *
   * The inverse of `project` is simpler than it looks: undo the vertical
   * foreshortening and the angle falls straight out of `atan2`, independent of
   * radius, so a point anywhere along a spoke maps to the same hour.
   *
   * Quantised to six minutes. A dial this size cannot resolve finer, and it
   * turns a continuous stream of pointer events into at most 240 distinct
   * states — which matters because every change re-renders a few thousand
   * projected path points.
   */
  const [scrub, setScrub] = useState<number | null>(null);
  /** The hour the reader has dragged the flagged task to, as a what-if. */
  const [proposed, setProposed] = useState<number | null>(null);
  const taskDrag = useRef<{ id: number | null }>({ id: null });

  /**
   * The hour under the pointer.
   *
   * `inBandOnly` is the difference between reading and moving: a reading taken
   * off the ring must actually be on it, whereas a task being dragged keeps
   * following the pointer even when it strays outside, because letting the mark
   * stick at the last good angle feels broken.
   */
  const hourFromPointer = (
    event: React.PointerEvent<HTMLDivElement>,
    inBandOnly: boolean,
  ): number | null => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return null;
    const scale = SIZE / rect.width;
    const px0 = (event.clientX - rect.left) * scale - C;
    const py0 = (event.clientY - rect.top) * scale - C;
    if (inBandOnly) {
      const radial = Math.hypot(px0, py0 / Math.sin(tilt));
      if (radial < AURORA_IN - 34 || radial > LABEL_R + 18) return null;
    }
    const angle = Math.atan2(py0 / Math.sin(tilt), px0);
    return (((angle + Math.PI / 2) / TAU) * 24 + 24) % 24;
  };

  const updateScrub = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!finePointer) return;
    // Outside the band the reading would be invented, so there is not one.
    const hour = hourFromPointer(event, true);
    const at = hour === null ? null : Math.round(hour * 10) / 10;
    setScrub(at);
    // Finding the trough is the tour's second ask, and this is the only place
    // that knows it has been found.
    if (at !== null) {
      const reading = scoreAt(at);
      if (reading !== null && reading < THRESHOLD) signal("trough");
    }
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    // A task being dragged owns the gesture: neither the camera nor the
    // reading under the pointer should move while it does.
    if (taskDrag.current.id === event.pointerId) {
      const hour = hourFromPointer(event, false);
      if (hour !== null) {
        const at = Math.round(hour * 10) / 10;
        setProposed(at);
        // The tour's third ask: moved somewhere it would actually clear.
        const reading = scoreAt(at);
        if (reading !== null && reading >= THRESHOLD) signal("cleared");
      }
      return;
    }
    const state = drag.current;
    if (state.id !== event.pointerId) {
      updateScrub(event);
      return;
    }
    const dy = event.clientY - state.y;
    // A few pixels of slop, so a click on a task is a click and not a one-pixel
    // camera move that swallows it.
    if (!state.moved && Math.abs(dy) < 4) {
      updateScrub(event);
      return;
    }
    // Once the camera is moving, the reading under the pointer is meaningless.
    setScrub(null);
    if (!state.moved) {
      state.moved = true;
      // Capture keeps the drag alive when the pointer wanders off the dial, so
      // it is an enhancement rather than a requirement — and it throws for a
      // pointer the browser no longer considers active, which a cancelled or
      // already-released pointer can be. Letting that escape a React handler
      // would abort the drag mid-gesture and surface an error to the console,
      // so failing quietly and dragging on uncaptured is strictly better.
      try {
        event.currentTarget.setPointerCapture(event.pointerId);
      } catch {
        /* no active pointer — carry on without it */
      }
    }
    state.y = event.clientY;
    setTilt((t) => Math.max(TILT_MIN, Math.min(TILT_MAX, t - dy * 0.0035)));
  };

  const endDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (taskDrag.current.id === event.pointerId) {
      taskDrag.current = { id: null };
      // The proposal stays on screen after release. Dropping it back the
      // instant you let go would make the whole gesture unreadable — you would
      // never see the answer you dragged for.
      dragged.current = true;
      window.setTimeout(() => {
        dragged.current = false;
      }, 0);
      return;
    }
    const state = drag.current;
    if (state.id !== event.pointerId) return;
    if (state.moved) {
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        /* already gone */
      }
    }
    // Cleared on the next tick so the click this pointer-up is about to raise
    // can still see that it came from a drag.
    const wasDrag = state.moved;
    drag.current = { id: null, y: 0, moved: false };
    if (wasDrag) {
      dragged.current = true;
      window.setTimeout(() => {
        dragged.current = false;
      }, 0);
    }
  };

  const curve = crew?.curve ?? [];
  const samples: Sample[] = curve.map((p) => ({
    h: hoursSince(windowStart, p.at),
    score: p.score,
    asleep: p.asleep,
    low: p.in_circadian_low,
  }));

  // Three pieces that tile the whole ring and meet exactly on the boundaries.
  const pieces = [
    { list: between(samples, 0, 6), near: true },
    { list: between(samples, 6, 18), near: false },
    { list: between(samples, 18, 24), near: true },
  ];

  /**
   * The curve's own value at an arbitrary hour, linearly interpolated between
   * the two samples either side of it. The engine publishes the curve at a
   * fixed cadence; reading between those points is interpolation of real data,
   * not a second opinion about it.
   */
  const scoreAt = (hour: number): number | null => {
    if (samples.length === 0) return null;
    if (samples.length === 1) return samples[0].score;
    for (let i = 0; i < samples.length - 1; i++) {
      const lo = samples[i];
      const hi = samples[i + 1];
      if (hour >= lo.h && hour <= hi.h) {
        const span = hi.h - lo.h;
        const t = span > 0 ? (hour - lo.h) / span : 0;
        return lo.score + (hi.score - lo.score) * t;
      }
    }
    return hour < samples[0].h ? samples[0].score : samples[samples.length - 1].score;
  };

  /** The wall clock that many hours into the window. */
  const clockAt = (hour: number) => {
    const at = new Date(new Date(windowStart).getTime() + hour * 3_600_000);
    return `${at.toISOString().slice(11, 16)}Z`;
  };

  const scrubScore = scrub === null ? null : scoreAt(scrub);
  const scrubPoint =
    scrub === null || scrubScore === null ? null : project(scrub, radiusFor(scrubScore), tilt);

  const circadian = runs(samples.map((s) => ({ h: s.h, flag: s.low })));
  const sleep = runs(samples.map((s) => ({ h: s.h, flag: s.asleep })));
  const mine = tasks.filter((t) => !crew || t.assigned_to === crew.crew_member);
  const flagged =
    mine.find((t) => t.situation_id && t.situation_id === selectedSituation) ??
    mine.find((t) => t.raises_situation);

  /** Everything on one side of the planet, drawn once per side. */
  const Ring = ({ near }: { near: boolean }) => (
    <>
      {/* The floor the ribbon stands on. */}
      {halves(0, 24)
        .filter((h) => h.near === near)
        .map((h, i) => (
          <path
            key={`in${i}`}
            d={ringPath(h.from, h.to, AURORA_IN, tilt)}
            fill="none"
            stroke="#fff"
            strokeOpacity={near ? 0.08 : 0.05}
          />
        ))}

      {/* The execution threshold. Anything inside it is a reading below the
          line — which is the shape an operator learns to look for. */}
      {halves(0, 24)
        .filter((h) => h.near === near)
        .map((h, i) => (
          <path
            key={`th${i}`}
            d={ringPath(h.from, h.to, radiusFor(THRESHOLD), tilt)}
            fill="none"
            stroke="var(--warn)"
            strokeOpacity={near ? 0.42 : 0.22}
            strokeWidth={1}
            strokeDasharray="2 5"
          />
        ))}

      {/* Predicted alertness. */}
      {pieces
        .filter((p) => p.near === near)
        .map((p, i) => {
          const d = ribbonPath(p.list, tilt);
          if (!d) return null;
          return <path key={`rb${i}`} d={d} fill="url(#od-aurora)" opacity={near ? 1 : 0.62} />;
        })}
      {pieces
        .filter((p) => p.near === near)
        .map((p, i) => (
          <g key={`ed${i}`} opacity={near ? 1 : 0.55}>
            <EdgeArc
              d={p.list.length > 1 ? polyline(p.list.map((s) => project(s.h, radiusFor(s.score), tilt))) : ""}
              animate={motionOK}
            />
          </g>
        ))}

      {/* Where the body clock and the roster put this person. Drawn outside the
          band so they annotate the day rather than colour the reading. */}
      {sleep.flatMap(([a, b], i) =>
        halves(a, b)
          .filter((h) => h.near === near)
          .map((h, j) => (
            <path
              key={`sl${i}-${j}`}
              d={ringPath(h.from, h.to, BAND_R, tilt)}
              fill="none"
              stroke="var(--accent)"
              strokeOpacity={near ? 0.5 : 0.26}
              strokeWidth={5}
              strokeLinecap="round"
            />
          )),
      )}
      {circadian.flatMap(([a, b], i) =>
        halves(a, b)
          .filter((h) => h.near === near)
          .map((h, j) => (
            <path
              key={`cl${i}-${j}`}
              d={ringPath(h.from, h.to, BAND_R - 9, tilt)}
              fill="none"
              stroke="var(--bad)"
              strokeOpacity={near ? 0.55 : 0.28}
              strokeWidth={4}
              strokeLinecap="round"
            />
          )),
      )}

      {/* Hour graticule. Every hour a tick. */}
      {Array.from({ length: 24 }, (_, h) => h)
        .filter((h) => isNear(h) === near)
        .map((h) => {
          const major = h % 3 === 0;
          const a = project(h, major ? 200 : 203, tilt);
          const b = project(h, 207, tilt);
          const fade = near ? 1 : 0.5;
          return (
            <line
              key={h}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="#fff"
              strokeOpacity={(major ? 0.3 : 0.13) * fade}
              strokeWidth={major ? 1.2 : 1}
            />
          );
        })}
    </>
  );

  return (
    <div
      ref={box}
      className={clsx("relative w-full", loading && "opacity-60 transition-opacity")}
      style={{ touchAction: "pan-y" }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onPointerLeave={(event) => {
        setScrub(null);
        endDrag(event);
      }}
    >
      {/* The planet, in its own square box centred on the dial. Real, lit, and
          turning — and dimmed, because on the landing the planet is the subject
          and here it is the thing the window goes round. Its own orbit track is
          off: this dial is the orbit.

          Deliberately the room rather than a readout, and dimmed until it
          reads that way. It carries no data -- the ring does. The honest way
          to make it carry some, marking the ~16 terminator crossings a crew
          in low orbit actually sees in a day, is not available here: the API
          does not publish the orbital phase, and evenly spaced ticks would
          assert a schedule nobody computed. Better an admitted backdrop than
          an invented instrument. */}
      <div
        className="pointer-events-none absolute z-0"
        style={{
          left: `${((C - GLOBE_BOX / 2) / SIZE) * 100}%`,
          top: `${((C - GLOBE_BOX / 2) / SIZE) * 100}%`,
          width: `${(GLOBE_BOX / SIZE) * 100}%`,
          height: `${(GLOBE_BOX / SIZE) * 100}%`,
        }}
      >
        <Earth
          className="absolute inset-0 opacity-[0.4]"
          placement={{ cx: 0.5, cy: 0.5, r: PLANET_R / GLOBE_BOX }}
          orbit={false}
          handleKey="__havenDialEarth"
        />
      </div>

      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="relative z-10 w-full"
        style={{ cursor: finePointer ? "ns-resize" : undefined }}
        role="img"
        aria-label={
          crew
            ? `Predicted alertness for ${crew.name} across the 24-hour window, with ${mine.length} assigned tasks placed at their scheduled hour.`
            : "Predicted alertness dial"
        }
      >
        <defs>
          {/* The ribbon's glow, squashed by exactly the same factor as the
              geometry.

              Left as a screen-space circle it goes wrong the moment the ring
              tilts: its rings stop lining up with the band they are shading, so
              the outer stops land near the ring's left and right extremes while
              the nearly transparent inner stops smear across the top and
              bottom — which paints the planet with a flat grey lens instead of
              lighting the band. Scaling the gradient about the centre by
              `sin(tilt)` puts its iso-lines back on the projected ring, so an
              offset means the same orbital radius everywhere on it again. */}
          <radialGradient
            id="od-aurora"
            gradientUnits="userSpaceOnUse"
            cx={C}
            cy={C}
            r={AURORA_OUT}
            gradientTransform={`translate(0 ${C}) scale(1 ${Math.sin(tilt).toFixed(4)}) translate(0 ${-C})`}
          >
            <stop
              offset={`${(AURORA_IN / AURORA_OUT) * 100}%`}
              stopColor="color-mix(in oklab, var(--accent) 5%, transparent)"
            />
            <stop offset="82%" stopColor="var(--info)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--info)" stopOpacity="0.42" />
          </radialGradient>
          <filter id="od-glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Occlusion. Black hides, white keeps, and the gradient softens the
              cut so a hard circle does not saw across the sphere's limb — which
              is lit and slightly translucent at the edge, not a flat disc. */}
          <radialGradient id="od-occluder">
            <stop offset="86%" stopColor="#000" />
            <stop offset="100%" stopColor="#fff" />
          </radialGradient>
          <mask id="od-behind-planet">
            <rect x="0" y="0" width={SIZE} height={SIZE} fill="#fff" />
            <circle cx={C} cy={C} r={PLANET_R + 4} fill="url(#od-occluder)" />
          </mask>
        </defs>

        {/* The far half, genuinely behind the sphere. */}
        <g mask="url(#od-behind-planet)">
          <Ring near={false} />
        </g>

        {/* The near half, over it. */}
        <Ring near />

        {/* Hour labels. Chrome, not geometry: they ride the ring but are never
            masked and never scale, because a label you cannot read has failed
            at the only job it has. The tilt floor keeps them clear of the
            sphere at every angle the reader can reach. */}
        {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => {
          const p = project(h, LABEL_R, tilt);
          return (
            <text
              key={h}
              x={p.x}
              y={p.y}
              textAnchor="middle"
              dominantBaseline="central"
              className="mono"
              fontSize={px(11)}
              fill="var(--ink-3)"
              opacity={isNear(h) ? 1 : 0.72}
              letterSpacing="0.06em"
            >
              {String(h).padStart(2, "0")}
            </text>
          );
        })}

        {/* The scrub hand. A clock face invites being read at a moment, and the
            dial had no way to answer — the curve's shape was legible but no
            single hour on it was. Sweeping the ring puts a hand on the hour
            under the pointer and a dot where the curve is at that instant,
            which is the product's whole claim made touchable: you can watch the
            reading fall into the trough and see the task sitting in it.

            Drawn beneath the task markers so probing the day never hides the
            thing the day is about. */}
        {scrubPoint && scrubScore !== null ? (
          <g pointerEvents="none">
            <line
              x1={project(scrub as number, AURORA_IN - 26, tilt).x}
              y1={project(scrub as number, AURORA_IN - 26, tilt).y}
              x2={scrubPoint.x}
              y2={scrubPoint.y}
              stroke="var(--ink)"
              strokeOpacity={0.34}
              strokeWidth={1}
            />
            <circle
              cx={scrubPoint.x}
              cy={scrubPoint.y}
              r={px(4)}
              fill="var(--void-deep)"
              stroke="var(--ink)"
              strokeWidth={px(1.6)}
            />
          </g>
        ) : null}

        {/* Tasks, at their hour and at the curve's radius. Never occluded — see
            the header. Depth is carried by size and opacity alone, so the mark
            still plots exactly where its score says it does. */}
        {/* Where the flagged task really is, while a proposal is being tried
            against another hour. Without it the reader loses the anchor the
            comparison is against. */}
        {proposed !== null && flagged
          ? (() => {
              const gh = hoursSince(windowStart, flagged.scheduled);
              const gp = project(gh, radiusFor(flagged.predicted_alertness), tilt);
              return (
                <g pointerEvents="none" opacity={0.42}>
                  <circle
                    cx={gp.x}
                    cy={gp.y}
                    r={px(5.5)}
                    fill="none"
                    stroke="var(--ink-3)"
                    strokeWidth={px(1.6)}
                    strokeDasharray="2 3"
                  />
                </g>
              );
            })()
          : null}

        {mine.map((task) => {
          const isSubject = !!flagged && flagged.task_id === task.task_id;
          const moved = isSubject && proposed !== null;
          const realHour = hoursSince(windowStart, task.scheduled);
          // A proposed task is plotted against the curve's own value at the
          // hour it was dragged to — the engine's published reading, not a new
          // one invented here.
          const h = moved ? (proposed as number) : realHour;
          const score = moved
            ? (scoreAt(proposed as number) ?? task.predicted_alertness)
            : task.predicted_alertness;
          const p = project(h, radiusFor(score), tilt);
          const tone = task.raises_situation ? toneOf(task.risk_level) : "ok";
          const color = moved
            ? score >= THRESHOLD
              ? "var(--ok)"
              : "var(--warn)"
            : TONE_VAR[tone];
          const selected = !!task.situation_id && task.situation_id === selectedSituation;
          const clickable = !!task.situation_id;
          const draggable = isSubject && finePointer;
          // A sixth either way across the ring: enough to read as depth, not
          // enough to be mistaken for a difference in the reading.
          const depth = 1 + p.depth * 0.16;
          const behind = !isNear(h) && Math.hypot(p.x - C, p.y - C) < PLANET_R;
          return (
            <g
              key={task.task_id}
              role={clickable ? "button" : undefined}
              tabIndex={clickable ? 0 : undefined}
              aria-label={`${task.label} at ${utcTime(task.scheduled)}, predicted alertness ${task.predicted_alertness.toFixed(2)}, ${task.criticality} criticality${draggable ? ". Drag around the dial to try it at another hour." : ""}`}
              className={clsx(
                draggable ? "cursor-grab" : clickable ? "cursor-pointer" : "cursor-default",
              )}
              opacity={behind ? 0.5 : 1}
              onPointerDown={(event) => {
                if (!draggable) return;
                // Claim the gesture before the wrapper reads it as a camera move.
                event.stopPropagation();
                taskDrag.current = { id: event.pointerId };
                setScrub(null);
                setProposed(realHour);
                try {
                  event.currentTarget.setPointerCapture(event.pointerId);
                } catch {
                  /* no active pointer — the wrapper still sees the moves */
                }
              }}
              onClick={() => {
                if (dragged.current) return;
                if (clickable) onSelectSituation(task.situation_id as string);
              }}
              onKeyDown={(event) => {
                if (!clickable) return;
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectSituation(task.situation_id as string);
                }
              }}
              onPointerEnter={() => setHovered(task.task_id)}
              onPointerLeave={() => setHovered((id) => (id === task.task_id ? null : id))}
              onFocus={() => setHovered(task.task_id)}
              onBlur={() => setHovered((id) => (id === task.task_id ? null : id))}
            >
              <circle cx={p.x} cy={p.y} r={px(17)} fill="transparent" />
              {task.raises_situation ? (
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={px(12) * depth}
                  fill={color}
                  opacity={0.22}
                  className={selected ? "breathe" : undefined}
                  style={{ transformOrigin: `${p.x}px ${p.y}px`, transformBox: "view-box" }}
                />
              ) : null}
              <circle
                cx={p.x}
                cy={p.y}
                r={(selected ? px(7.5) : px(5.5)) * depth}
                fill={selected ? color : "var(--void-deep)"}
                stroke={color}
                strokeWidth={px(selected ? 2 : 2.2)}
                style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: "r .3s ease" }}
              />
            </g>
          );
        })}
      </svg>

      {/* The reading under the hand. Yields to a task tooltip rather than
          stacking with it — the task is the more specific answer to the same
          question, and two labels over one mark is neither of them. */}
      {scrubPoint && scrubScore !== null && !hovered ? (
        <div
          aria-hidden
          className="pointer-events-none absolute z-20 w-max rounded-[var(--radius-xs)] px-2 py-1"
          style={{
            left: `${(scrubPoint.x / SIZE) * 100}%`,
            top: `${(scrubPoint.y / SIZE) * 100}%`,
            transform: "translate(-50%, calc(-100% - 10px))",
            background: "color-mix(in oklab, var(--void-deep) 90%, transparent)",
            boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.1)",
          }}
        >
          <span className="mono text-[11px] text-[var(--ink-3)]">{clockAt(scrub as number)}</span>
          <span
            className="readout ml-1.5 text-[12px]"
            style={{ color: scrubScore < THRESHOLD ? "var(--warn)" : "var(--ink)" }}
          >
            {scrubScore.toFixed(2)}
          </span>
        </div>
      ) : null}

      {/* What the pointer is on. Positioned in per cent of a square container,
          which is exactly how the SVG places the mark it belongs to — so the
          label tracks the node at every width and every tilt without measuring
          anything. */}
      {mine.map((task) => {
        if (task.task_id !== hovered) return null;
        const h = hoursSince(windowStart, task.scheduled);
        const p = project(h, radiusFor(task.predicted_alertness), tilt);
        return (
          <div
            key={task.task_id}
            role="tooltip"
            className="glass-3 rise pointer-events-none absolute z-30 w-max max-w-[190px] rounded-[var(--radius-xs)] px-2.5 py-2"
            style={{
              left: `${(p.x / SIZE) * 100}%`,
              top: `${(p.y / SIZE) * 100}%`,
              transform: "translate(-50%, calc(-100% - 14px))",
              background: "color-mix(in oklab, var(--void-deep) 92%, transparent)",
              backdropFilter: "blur(14px)",
            }}
          >
            <div className="mono text-[11px] text-[var(--ink-3)]">
              {utcTime(task.scheduled)} · {task.criticality}
            </div>
            <div className="mt-1 text-[12px] leading-snug text-[var(--ink)]">{task.label}</div>
            <div
              className="readout mt-1 text-[12px]"
              style={{ color: TONE_VAR[task.raises_situation ? toneOf(task.risk_level) : "ok"] }}
            >
              {task.predicted_alertness.toFixed(2)} predicted
            </div>
          </div>
        );
      })}

      {/* The centre reads as part of the scene, so it is HTML rather than SVG
          text: real font metrics, real ellipsis, real selection. */}
      <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center">
        <div className="relative max-w-[52%] text-center">
          {/* A well under the type. There is a lit sphere behind this now, and
              §8's lesson is that contrast over a canvas cannot be reasoned
              about from CSS alone — it has to be composited first. Putting an
              opaque enough ground under the text is cheaper than measuring, and
              it holds at every tilt and every frame of the terminator. */}
          <div
            aria-hidden
            className="absolute -inset-x-10 -inset-y-8 -z-10"
            style={{
              background:
                "radial-gradient(closest-side, color-mix(in oklab, var(--void-deep) 90%, transparent) 52%, transparent 100%)",
            }}
          />
          {proposed !== null && flagged ? (
            /* The what-if.

               Fatigue means nothing except against what happens next, which the
               page has been asserting in prose and could not let anybody test.
               Dragging the flagged task round the clock answers it against the
               engine's own published curve and the same 0.70 line the dial
               already draws.

               It is scrupulously labelled as a projection. Nothing here asked
               the engine to re-evaluate: the rules, the roster and the checker
               all ran against the real scheduled time, and a reader who came
               away thinking the console had re-decided the case would have
               learned something false. */
            (() => {
              const score = scoreAt(proposed) ?? 0;
              const clears = score >= THRESHOLD;
              const colour = clears ? "var(--ok)" : "var(--warn)";
              return (
                <>
                  <div className="label text-[11px] text-[var(--ink-3)]">Proposed</div>
                  <div
                    className="readout mt-1 leading-none"
                    style={{ fontSize: Math.max(21, Math.min(30, width * 0.058)), color: colour }}
                  >
                    {clockAt(proposed)}
                  </div>
                  <div className="readout mt-1.5 text-[13px] text-[var(--ink-2)]">
                    {score.toFixed(2)} predicted
                  </div>
                  <div className="label mt-1.5" style={{ color: colour }}>
                    {clears ? "clears the line" : "still below the line"}
                  </div>
                  <button
                    type="button"
                    onClick={() => setProposed(null)}
                    className="pointer-events-auto mt-3 rounded-full px-2.5 py-1 text-[11px] text-[var(--ink-2)] transition-colors hover:text-[var(--ink)]"
                    style={{ boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.16)" }}
                  >
                    Put it back
                  </button>
                  <div className="mt-2 text-[11px] leading-snug text-[var(--ink-3)]">
                    A projection. HAVEN has not re-evaluated this.
                  </div>
                </>
              );
            })()
          ) : flagged ? (
            <>
              <div className="label text-[11px] text-[var(--ink-3)]">
                {flagged.raises_situation ? "Flagged task" : "Next task"}
              </div>
              <div
                className="readout mt-1 leading-none text-[var(--ink)]"
                style={{ fontSize: Math.max(21, Math.min(30, width * 0.058)) }}
              >
                {utcTime(flagged.scheduled)}
              </div>
              <div className="mt-2 text-[12px] leading-snug text-[var(--ink-2)] sm:text-[13px]">
                {flagged.label}
              </div>
              {/* The state as a word in its own colour, not a capsule around
                  one. A filled pill sitting on the planet was the loudest
                  object in the dial and the least information in it — the risk
                  level already reads from the marker's colour on the ring. */}
              <div
                className="label mt-2.5"
                style={{
                  color: TONE_VAR[flagged.raises_situation ? toneOf(flagged.risk_level) : "ok"],
                }}
              >
                {flagged.raises_situation ? `${flagged.risk_level} risk` : "cleared"}
              </div>
            </>
          ) : (
            <>
              <div className="label text-[11px]">24-hour window</div>
              <div className="mt-2 text-[13px] leading-snug text-[var(--ink-2)]">
                No task in this window collided with a low.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * The dial's key. Small, and beside the dial rather than over it.
 *
 * Two things it used to get wrong. Four items on a `flex-wrap` broke 3 + 1 at
 * this column width, which is the ragged shelf a charting library leaves behind
 * — a fixed two-by-two grid breaks 2 + 2 at every width instead. And every
 * swatch was the same rounded dash, so the key said nothing about which mark it
 * stood for; now the threshold's swatch is dashed because the threshold is
 * dashed, and the two annotation arcs are drawn at their real weight.
 *
 * The swatches are strokes of a flat colour, not a gradient: §8 records that a
 * gradient in `objectBoundingBox` units cannot paint a horizontal line, because
 * the box has no height and the gradient degenerates to nothing.
 */
export function OrbitLegend({ className }: { className?: string }) {
  const items: { color: string; label: string; note?: string; dashed?: boolean; thick?: boolean }[] =
    [
      { color: "var(--info)", label: "Predicted alertness" },
      { color: "var(--warn)", label: "Execution threshold", note: "0.70", dashed: true },
      { color: "var(--bad)", label: "Circadian low", thick: true },
      { color: "var(--accent)", label: "Scheduled sleep", thick: true },
    ];
  return (
    <ul className={clsx("grid grid-cols-2 gap-x-5 gap-y-2", className)}>
      {items.map((item) => (
        <li
          key={item.label}
          className="flex min-w-0 items-center gap-2 text-[12px] text-[var(--ink-2)]"
        >
          <svg width="20" height="6" viewBox="0 0 20 6" aria-hidden className="shrink-0">
            <line
              x1="0.5"
              y1="3"
              x2="19.5"
              y2="3"
              stroke={item.color}
              strokeWidth={item.thick ? 4 : 1.8}
              strokeLinecap="round"
              strokeDasharray={item.dashed ? "1.5 3" : undefined}
              strokeOpacity={item.thick ? 0.7 : 1}
            />
          </svg>
          <span className="truncate">{item.label}</span>
          {item.note ? (
            <span className="readout shrink-0 text-[11px] text-[var(--ink-3)]">{item.note}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
