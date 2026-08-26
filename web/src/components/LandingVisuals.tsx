"use client";

import { useId } from "react";

/**
 * The landing page's arguments, drawn.
 *
 * The page was 1,193 words with one large graphic on it, and that graphic was
 * the fake planet. Five consecutive sections each spent two hundred words
 * describing something that is inherently a picture: a line numbers may cross
 * in only one direction, a curve falling away from what a person reports about
 * themselves, a sequence that stops at a human. Prose is the wrong instrument
 * for all three.
 *
 * The curves below are computed, not drawn. `alertness()` is the same shape of
 * model the engine runs — a homeostatic term that decays with time awake plus a
 * circadian oscillation — so the dip lands at four in the morning because the
 * arithmetic puts it there, not because a designer moved a bezier handle.
 */

/* ==========================================================================
   The alertness curve
   ==========================================================================
   Three-Process Model, in the small. Alertness is a homeostatic component that
   falls the longer you have been awake, plus a circadian oscillation that is
   indifferent to how tired you are. The two together are the reason a rested
   person can still be dangerous at 04:00, which is the entire premise of the
   circadian_trap case in the console.
*/

/** Clock hour the crew member wakes. The window runs 24 h from here. */
const WAKE = 6;
/** Homeostatic time constant, hours. Sleep pressure builds the longer you are up. */
const TAU = 21;
/** Clock hour of the circadian peak; the trough sits twelve hours opposite. */
const PEAK_HOUR = 16;

/**
 * `t` is hours since waking. The two terms are indexed differently on purpose:
 * sleep pressure only knows how long you have been awake, and the body clock
 * only knows what time it is. They fall into step in the small hours, and that
 * coincidence is the whole reason a rested person can still be unsafe at 04:00.
 */
function alertness(t: number): number {
  const clock = (WAKE + t) % 24;
  const homeostatic = Math.exp(-t / TAU); // 1 → 0, slowly
  const circadian = Math.cos((2 * Math.PI * (clock - PEAK_HOUR)) / 24); // +1 peak, −1 trough
  const a = 0.3 + 0.46 * homeostatic + 0.2 * circadian;
  return Math.min(1, Math.max(0, a));
}

/** Hours-since-waking → the clock face, which is what a reader thinks in. */
const clockLabel = (t: number) => String(Math.round((WAKE + t) % 24)).padStart(2, "0");

/** What the same person says about themselves. Flat, because that is the point. */
const SELF_REPORT = 0.78;
/** The floor a flight rule sets for high-criticality work. */
const FLOOR = 0.55;

export function AlertnessGap({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const W = 760;
  const H = 268;
  const padL = 44;
  const padR = 20;
  const padT = 18;
  const padB = 34;

  const x = (h: number) => padL + (h / 24) * (W - padL - padR);
  const y = (a: number) => padT + (1 - a) * (H - padT - padB);

  const N = 240;
  const pts = Array.from({ length: N + 1 }, (_, i) => {
    const h = (i / N) * 24;
    return { h, a: alertness(h) };
  });

  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(p.h).toFixed(1)},${y(p.a).toFixed(1)}`).join("");
  // The shaded gap: the region where the person is worse than they think.
  const gapTop = pts.map((p) => `L${x(p.h).toFixed(1)},${y(Math.min(p.a, SELF_REPORT)).toFixed(1)}`).join("");
  const gap = `M${x(0)},${y(SELF_REPORT)}${gapTop}L${x(24)},${y(SELF_REPORT)}Z`;

  // The worst moment in the window, found rather than chosen.
  const worst = pts.reduce((m, p) => (p.a < m.a ? p : m), pts[0]);
  const worstClock = (WAKE + worst.h) % 24;
  const hh = String(Math.floor(worstClock)).padStart(2, "0");
  const mm = String(Math.round((worstClock % 1) * 60)).padStart(2, "0");
  // Past three-quarters across, the callout has to sit on the other side.
  const flip = worst.h > 17;

  return (
    <figure className={className}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Predicted alertness falls through the night while self-reported alertness stays flat"
      >
        <title>Measured alertness against what the crew member reports</title>
        <defs>
          <linearGradient id={`${uid}-gap`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--warn)" stopOpacity="0.30" />
            <stop offset="100%" stopColor="var(--warn)" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id={`${uid}-line`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--ok)" />
            <stop offset="52%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--ok)" />
          </linearGradient>
        </defs>

        {/* hour grid */}
        {[0, 4, 8, 12, 16, 20, 24].map((h) => (
          <g key={h}>
            <line x1={x(h)} y1={padT} x2={x(h)} y2={H - padB}
              stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
            <text x={x(h)} y={H - 12} textAnchor="middle"
              className="mono" fontSize="11" fill="var(--ink-3)">
              {clockLabel(h)}
            </text>
          </g>
        ))}
        <text x={x(0)} y={H - 12} textAnchor="middle" fontSize="11"
          className="mono" fill="var(--ink-3)" opacity="0" aria-hidden="true" />

        {/* the gap between belief and fact */}
        <path d={gap} fill={`url(#${uid}-gap)`} />

        {/* what the person says */}
        <line x1={x(0)} y1={y(SELF_REPORT)} x2={x(24)} y2={y(SELF_REPORT)}
          stroke="var(--ink-3)" strokeWidth="1.5" strokeDasharray="5 5" />
        <text x={x(0.4)} y={y(SELF_REPORT) - 8} fontSize="12" fill="var(--ink-2)">
          “I’m fine”
        </text>

        {/* the rule's floor */}
        <line x1={x(0)} y1={y(FLOOR)} x2={x(24)} y2={y(FLOOR)}
          stroke="var(--bad)" strokeOpacity="0.55" strokeWidth="1.5" />
        <text x={x(11.6)} y={y(FLOOR) - 9} fontSize="12" textAnchor="middle" fill="var(--bad)">
          flight-rule floor {FLOOR.toFixed(2)}
        </text>

        {/* what the maths says */}
        <path d={line} fill="none" stroke={`url(#${uid}-line)`} strokeWidth="2.5"
          strokeLinecap="round" />

        {/* the worst moment */}
        <g>
          <line x1={x(worst.h)} y1={y(worst.a)} x2={x(worst.h)} y2={H - padB}
            stroke="var(--accent)" strokeOpacity="0.4" strokeWidth="1" strokeDasharray="3 3" />
          <circle cx={x(worst.h)} cy={y(worst.a)} r="5.5" fill="var(--accent)" />
          <circle cx={x(worst.h)} cy={y(worst.a)} r="11" fill="none"
            stroke="var(--accent)" strokeOpacity="0.35" strokeWidth="1.5" />
          {/* Below the dot, never beside it.

              Level with the marker the label sat exactly on the curve, which
              runs horizontally through the trough -- the line went straight
              through the type. Underneath is safe by construction rather than
              by luck: this marks the curve's global minimum, so no part of the
              curve is ever below it. The horizontal flip stays, so the text
              also clears the dashed drop-line rather than straddling it. */}
          <text
            x={x(worst.h) + (flip ? -12 : 12)}
            y={y(worst.a) + 26}
            textAnchor={flip ? "end" : "start"}
            fontSize="12.5"
            fill="var(--ink)"
          >
            {hh}:{mm} · {worst.a.toFixed(2)}
          </text>
        </g>

        {/* y axis, two labels only */}
        <text x={12} y={y(1) + 4} fontSize="11" className="mono" fill="var(--ink-3)">1.0</text>
        <text x={12} y={y(0.2) + 4} fontSize="11" className="mono" fill="var(--ink-3)">0.2</text>
      </svg>
      <figcaption className="mt-3 text-[13px] leading-relaxed text-[var(--ink-3)]">
        Awake since 06:00. The wedge is what they cannot feel — widest in the small hours, exactly
        when a slipped schedule puts the hardest task in front of them.
      </figcaption>
    </figure>
  );
}

/* ==========================================================================
   The hard line
   ==========================================================================
   The section this replaces spent 248 words explaining that numbers may cross
   in one direction only. It is a picture of a wall with a one-way gate in it.
*/

const CROSSING = [
  { label: "alertness", value: "0.31" },
  { label: "workload", value: "48.6" },
  { label: "sleep debt", value: "14.1 h" },
];

export function HardLine({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const W = 760;
  const H = 300;
  const mid = W / 2;

  return (
    <figure className={className}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        <title>
          Numbers pass from the deterministic tier to the model. Nothing passes back.
        </title>
        <defs>
          <linearGradient id={`${uid}-wall`} gradientUnits="userSpaceOnUse"
            x1="0" y1="10" x2="0" y2={H - 10}>
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0" />
            <stop offset="18%" stopColor="var(--accent)" stopOpacity="0.85" />
            <stop offset="82%" stopColor="var(--accent)" stopOpacity="0.85" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={`${uid}-l`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--ok)" stopOpacity="0.05" />
            <stop offset="100%" stopColor="var(--ok)" stopOpacity="0.14" />
          </linearGradient>
          <linearGradient id={`${uid}-r`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--info)" stopOpacity="0.14" />
            <stop offset="100%" stopColor="var(--info)" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {/* the two territories */}
        <rect x="0" y="34" width={mid - 26} height={H - 68} rx="14" fill={`url(#${uid}-l)`} />
        <rect x={mid + 26} y="34" width={mid - 26} height={H - 68} rx="14" fill={`url(#${uid}-r)`} />

        <text x="18" y="22" fontSize="11" letterSpacing="2.2" fill="var(--ok)">
          ORDINARY MATHS
        </text>
        <text x={W - 18} y="22" fontSize="11" letterSpacing="2.2" textAnchor="end" fill="var(--info)">
          THE MODEL
        </text>

        {/* the wall */}
        <rect x={mid - 1.4} y="10" width="2.8" height={H - 20} fill={`url(#${uid}-wall)`} />
        <rect x={mid - 9} y="10" width="18" height={H - 20} fill={`url(#${uid}-wall)`}
          opacity="0.13" style={{ filter: "blur(6px)" }} />

        {/* numbers crossing, left to right */}
        {CROSSING.map((row, i) => {
          const y = 78 + i * 52;
          return (
            <g key={row.label}>
              <text x="26" y={y - 17} fontSize="12" fill="var(--ink-3)">
                {row.label}
              </text>
              <text x="26" y={y + 10} fontSize="21" className="readout" fill="var(--ink)">
                {row.value}
              </text>
              <line x1="150" y1={y + 2} x2={mid - 8} y2={y + 2}
                stroke="var(--ok)" strokeOpacity="0.45" strokeWidth="1.5" strokeDasharray="4 4" />
              <path d={`M${mid - 10},${y - 3}l7,5l-7,5z`} fill="var(--ok)" opacity="0.75" />
              {/* a value travelling the allowed direction */}
              <circle r="3.5" cy={y + 2} fill="var(--ok)">
                <animate attributeName="cx" from="150" to={mid - 12} dur="2.7s"
                  begin={`${i * 0.9}s`} repeatCount="indefinite" />
                <animate attributeName="opacity" values="0;1;1;0" dur="2.7s"
                  begin={`${i * 0.9}s`} repeatCount="indefinite" />
              </circle>
              <text x={mid + 22} y={y + 6} fontSize="13" fill="var(--ink-2)">
                quoted, never altered
              </text>
            </g>
          );
        })}

        {/* the blocked direction */}
        <g transform={`translate(0,${H - 52})`}>
          <text x={W - 26} y="-14" fontSize="12" textAnchor="end" fill="var(--ink-3)">
            an invented figure
          </text>
          <line x1={W - 150} y1="4" x2={mid + 16} y2="4"
            stroke="var(--bad)" strokeOpacity="0.5" strokeWidth="1.5" strokeDasharray="4 4" />
          <g stroke="var(--bad)" strokeWidth="2.5" strokeLinecap="round">
            <line x1={mid - 9} y1="-5" x2={mid + 9} y2="13" />
            <line x1={mid + 9} y1="-5" x2={mid - 9} y2="13" />
          </g>
          <text x={mid - 24} y="8" fontSize="13" textAnchor="end" fill="var(--bad)">
            refused in code
          </text>
        </g>
      </svg>
    </figure>
  );
}

/* ==========================================================================
   The pipeline
   ==========================================================================
   Five stages on one rail, with the last one visibly not a machine.
*/

const STAGES: { n: string; title: string; note: string }[] = [
  { n: "01", title: "Listen", note: "Sleep, duty, workload" },
  { n: "02", title: "Calculate", note: "Published models only" },
  { n: "03", title: "Read the manual", note: "Search the procedures" },
  { n: "04", title: "Check the schedule", note: "Can anyone else do it?" },
  { n: "05", title: "Hand it over", note: "A person decides" },
];

export function PipelineRail({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const W = 900;
  const H = 150;
  const y = 58;
  // Wide enough that the end stages' captions stay inside the box. The
  // longest is 111 units across and is centred on its dot, so anything under
  // ~56 clips it: "Sleep, duty, workload" was losing its first two letters.
  const x0 = 66;
  const x1 = W - 66;
  const step = (x1 - x0) / (STAGES.length - 1);

  return (
    <figure className={className}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        <title>Five stages. The last one is a person.</title>
        <defs>
          <linearGradient id={`${uid}-rail`} gradientUnits="userSpaceOnUse"
            x1={x0} y1="0" x2={x1} y2="0">
            <stop offset="0%" stopColor="var(--ok)" stopOpacity="0.75" />
            <stop offset="72%" stopColor="var(--info)" stopOpacity="0.8" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.9" />
          </linearGradient>
        </defs>

        {/* A rect, not a line: a horizontal line has a zero-height bounding box,
            which makes an objectBoundingBox gradient degenerate. */}
        <rect x={x0} y={y - 1} width={x1 - x0} height="2" fill={`url(#${uid}-rail)`} />

        {/* one packet of work travelling the whole rail */}
        <circle r="4.5" cy={y} fill="var(--accent)">
          <animate attributeName="cx" from={x0} to={x1} dur="6s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;1;1;0" dur="6s" repeatCount="indefinite" />
        </circle>

        {STAGES.map((s, i) => {
          const cx = x0 + i * step;
          const last = i === STAGES.length - 1;
          return (
            <g key={s.n}>
              {last ? (
                // A person, not a node. The shape change is the argument.
                <g>
                  <circle cx={cx} cy={y - 7} r="5" fill="var(--accent)" />
                  <path d={`M${cx - 9},${y + 8} a9,9 0 0 1 18,0`} fill="var(--accent)" />
                </g>
              ) : (
                <>
                  <circle cx={cx} cy={y} r="9" fill="var(--void-deep)"
                    stroke="var(--ink-3)" strokeWidth="1.5" />
                  <circle cx={cx} cy={y} r="3" fill="var(--ok)" />
                </>
              )}
              <text x={cx} y={y - 26} textAnchor="middle" fontSize="11"
                className="mono" fill={last ? "var(--accent)" : "var(--ink-3)"}>
                {s.n}
              </text>
              <text x={cx} y={y + 34} textAnchor="middle" fontSize="13" fontWeight="500"
                fill={last ? "var(--accent)" : "var(--ink)"}>
                {s.title}
              </text>
              <text x={cx} y={y + 52} textAnchor="middle" fontSize="11.5" fill="var(--ink-3)">
                {s.note}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

/* ==========================================================================
   The three layers of the console
   ========================================================================== */

const LAYERS = [
  { k: "The answer", v: "What to do, in plain words", tone: "var(--accent)" },
  { k: "How it decided", v: "Searched, offered, allowed, cited", tone: "var(--info)" },
  { k: "The evidence", v: "Every rule, condition and hash", tone: "var(--ok)" },
];

/**
 * Three bands, and the spacing has to answer to the slant.
 *
 * The cost label used to sit at a fixed `W - 52`, which is exactly where the
 * band's leaning right edge passes at that height -- so "no clicks" was
 * printed on the border rather than inside it. A skewed box has no single
 * right margin: the edge moves as you go down it, so anything aligned to it
 * has to be positioned from the edge at *its own* baseline, not from the box.
 *
 * The bands were also 46 tall carrying two lines of type plus their leading,
 * which left the title and the subtitle almost touching, and the whole stack
 * finished 54 units short of the viewBox with the slack all dumped at the
 * bottom. Bands are 52 now, the type has room, and the box ends where the
 * drawing does.
 */
const BAND_H = 56;
const BAND_STEP = 72;
const BAND_SKEW = 26;
const BAND_TOP = 20;

export function LayerStack({ className }: { className?: string }) {
  const W = 620;
  const H = BAND_TOP * 2 + BAND_STEP * (LAYERS.length - 1) + BAND_H;

  /** Where the leaning right edge sits, this far down a band. */
  const rightEdgeAt = (dy: number) => W - 40 - BAND_SKEW * (dy / BAND_H);

  return (
    <figure className={className}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        <title>One screen, readable at three depths</title>
        {LAYERS.map((l, i) => {
          const inset = i * 46;
          const y = BAND_TOP + i * BAND_STEP;
          // Both baselines, and the cost label rides the first one so it reads
          // as an annotation of the layer's name rather than floating between
          // the two lines with nothing to align to.
          // 21 apart rather than 18: at 14px over 12px the two em boxes were
          // leaving 2.6px between them, which reads as one crowded block.
          const titleDy = 21;
          const subDy = 42;
          return (
            <g key={l.k}>
              <path
                d={`M${60 + inset},${y} L${W - 40},${y} L${W - 40 - BAND_SKEW},${y + BAND_H} L${34 + inset},${y + BAND_H} Z`}
                fill={`color-mix(in oklab, ${l.tone} ${14 - i * 3}%, transparent)`}
                stroke={`color-mix(in oklab, ${l.tone} 40%, transparent)`}
                strokeWidth="1"
              />
              <text x={78 + inset} y={y + titleDy} fontSize="14" fontWeight="500" fill={l.tone}>
                {l.k}
              </text>
              <text x={78 + inset} y={y + subDy} fontSize="12" fill="var(--ink-2)">
                {l.v}
              </text>
              <text
                x={rightEdgeAt(titleDy) - 18}
                y={y + titleDy}
                fontSize="11"
                textAnchor="end"
                className="mono"
                fill="var(--ink-3)"
              >
                {i === 2 ? "one click" : "no clicks"}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
