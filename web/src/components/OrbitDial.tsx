"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { CrewReadiness, TimelineTask } from "@/lib/types";
import { useMotionOK, useTilt } from "@/lib/motion";
import { useElementWidth } from "@/lib/useElementWidth";
import { Chip, TONE_VAR, hoursSince, toneOf, utcTime } from "./ui";

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
 * So: twenty-four hours around the circle, midnight at the top. The band is
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
 */

const SIZE = 460;
const C = SIZE / 2;

const AURORA_IN = 132;
const AURORA_OUT = 188;
const BAND_R = 198;
const LABEL_R = 214;
const PLANET_R = 112;
const THRESHOLD = 0.7;

const radiusFor = (score: number) => AURORA_IN + Math.max(0, Math.min(1, score)) * (AURORA_OUT - AURORA_IN);

function point(hour: number, radius: number): [number, number] {
  const angle = ((hour / 24) * 360 - 90) * (Math.PI / 180);
  return [C + radius * Math.cos(angle), C + radius * Math.sin(angle)];
}

function arc(from: number, to: number, radius: number) {
  const [x0, y0] = point(from, radius);
  const [x1, y1] = point(to, radius);
  const large = to - from > 12 ? 1 : 0;
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${radius} ${radius} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
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

/** Continent blobs, laid out once. Two copies scroll to read as rotation. */
const LAND: [number, number, number, number, string][] = [
  [148, 176, 34, 20, "#2f7a58"],
  [186, 208, 22, 30, "#37855f"],
  [140, 250, 26, 16, "#6f7c46"],
  [206, 286, 30, 18, "#2c6f52"],
  [258, 200, 26, 34, "#358059"],
  [296, 262, 20, 14, "#6d7a49"],
  [246, 310, 34, 14, "#2b6a4f"],
  [300, 178, 16, 12, "#3a8862"],
];

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
  const tilt = useTilt<HTMLDivElement>(3.5);
  const motionOK = useMotionOK();
  const edge = useRef<SVGPathElement>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  // The dial is drawn in viewBox units and scaled to whatever width it lands
  // in, which would shrink its labels and hit targets along with it. Dividing
  // by that scale gives marks a *constant on-screen* size instead: 11px type
  // and a 34px touch target at 300px wide and at 520px wide alike.
  const k = width > 0 ? SIZE / width : 1;
  const px = (onScreen: number) => onScreen * k;

  const curve = crew?.curve ?? [];
  const samples = curve.map((p) => ({
    h: hoursSince(windowStart, p.at),
    score: p.score,
    asleep: p.asleep,
    low: p.in_circadian_low,
  }));

  const auroraPath = (() => {
    if (samples.length < 2) return "";
    const outer = samples.map((s) => point(s.h, radiusFor(s.score)));
    const inner = [...samples].reverse().map((s) => point(s.h, AURORA_IN));
    const line = (pts: [number, number][]) =>
      pts.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
    return `${line(outer)} ${line(inner).replace(/^M/, "L")} Z`;
  })();

  const edgePath = (() => {
    if (samples.length < 2) return "";
    return samples
      .map((s, i) => {
        const [x, y] = point(s.h, radiusFor(s.score));
        return `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");
  })();

  // A path can only draw itself if it knows how long it is, and only the
  // rendered element knows that. Measured after commit, once per curve.
  useEffect(() => {
    const node = edge.current;
    if (!node || !motionOK) return;
    const length = node.getTotalLength();
    node.style.setProperty("--draw-length", String(Math.ceil(length)));
    node.style.strokeDasharray = String(Math.ceil(length));
  }, [motionOK, edgePath]);

  const circadian = runs(samples.map((s) => ({ h: s.h, flag: s.low })));
  const sleep = runs(samples.map((s) => ({ h: s.h, flag: s.asleep })));
  const mine = tasks.filter((t) => !crew || t.assigned_to === crew.crew_member);
  const flagged = mine.find((t) => t.situation_id && t.situation_id === selectedSituation) ?? mine.find((t) => t.raises_situation);

  return (
    <div
      ref={box}
      className={clsx("tilt relative w-full", loading && "opacity-60 transition-opacity")}
    >
      <div ref={tilt} className="tilt-inner">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="w-full"
        role="img"
        aria-label={
          crew
            ? `Predicted alertness for ${crew.name} across the 24-hour window, with ${mine.length} assigned tasks placed at their scheduled hour.`
            : "Predicted alertness dial"
        }
      >
        <defs>
          <radialGradient id="od-globe" cx="34%" cy="27%" r="80%">
            <stop offset="0%" stopColor="#4a97dc" />
            <stop offset="34%" stopColor="#1d4f88" />
            <stop offset="70%" stopColor="#0c2444" />
            <stop offset="100%" stopColor="#050a16" />
          </radialGradient>
          <radialGradient id="od-terminator" cx="74%" cy="80%" r="82%">
            <stop offset="30%" stopColor="rgba(0,0,0,0)" />
            <stop offset="100%" stopColor="rgba(0,0,0,0.88)" />
          </radialGradient>
          <radialGradient id="od-atmo" cx="50%" cy="50%" r="50%">
            <stop offset="70%" stopColor="var(--atmo)" stopOpacity="0" />
            <stop offset="93%" stopColor="var(--atmo)" stopOpacity="0.26" />
            <stop offset="100%" stopColor="var(--atmo)" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="od-bloom" cx="50%" cy="50%" r="50%">
            <stop offset="40%" stopColor="color-mix(in oklab, var(--iris) 26%, transparent)" />
            <stop offset="100%" stopColor="color-mix(in oklab, var(--iris) 0%, transparent)" />
          </radialGradient>
          <radialGradient id="od-aurora" cx="50%" cy="50%" r="50%">
            <stop offset={`${(AURORA_IN / AURORA_OUT) * 100}%`} stopColor="color-mix(in oklab, var(--iris) 5%, transparent)" />
            <stop offset="82%" stopColor="var(--info)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--info)" stopOpacity="0.42" />
          </radialGradient>
          <clipPath id="od-clip">
            <circle cx={C} cy={C} r={PLANET_R} />
          </clipPath>
          <filter id="od-soft" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3.4" />
          </filter>
          <filter id="od-glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Hour graticule. Every hour a tick, every third an hour label. */}
        <g>
          {Array.from({ length: 24 }, (_, h) => {
            const major = h % 3 === 0;
            const [x0, y0] = point(h, major ? 200 : 203);
            const [x1, y1] = point(h, 207);
            return (
              <line
                key={h}
                x1={x0}
                y1={y0}
                x2={x1}
                y2={y1}
                stroke="#fff"
                strokeOpacity={major ? 0.3 : 0.13}
                strokeWidth={major ? 1.2 : 1}
              />
            );
          })}
          {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => {
            const [x, y] = point(h, LABEL_R);
            return (
              <text
                key={h}
                x={x}
                y={y}
                textAnchor="middle"
                dominantBaseline="central"
                className="mono"
                fontSize={px(11)}
                fill="var(--ink-3)"
                letterSpacing="0.06em"
              >
                {String(h).padStart(2, "0")}
              </text>
            );
          })}
        </g>

        {/* Where the body clock and the roster put this person. Drawn outside
            the band so they annotate the day rather than colour the reading. */}
        {sleep.map(([a, b], i) => (
          <path
            key={`sl${i}`}
            d={arc(a, b, BAND_R)}
            fill="none"
            stroke="var(--iris)"
            strokeOpacity={0.5}
            strokeWidth={5}
            strokeLinecap="round"
          />
        ))}
        {circadian.map(([a, b], i) => (
          <path
            key={`cl${i}`}
            d={arc(a, b, BAND_R - 9)}
            fill="none"
            stroke="var(--bad)"
            strokeOpacity={0.55}
            strokeWidth={4}
            strokeLinecap="round"
          />
        ))}

        {/* The execution threshold, as a ring. Anything inside it is a reading
            below the line — which is the shape an operator learns to look for. */}
        <circle
          cx={C}
          cy={C}
          r={radiusFor(THRESHOLD)}
          fill="none"
          stroke="var(--warn)"
          strokeOpacity={0.42}
          strokeWidth={1}
          strokeDasharray="2 5"
        />
        <circle cx={C} cy={C} r={AURORA_IN} fill="none" stroke="#fff" strokeOpacity={0.08} />

        {/* Predicted alertness. */}
        {auroraPath ? (
          <>
            <path d={auroraPath} fill="url(#od-aurora)" />
            <path
              ref={edge}
              d={edgePath}
              fill="none"
              stroke="var(--info)"
              strokeWidth={1.8}
              strokeOpacity={0.92}
              strokeLinejoin="round"
              filter="url(#od-glow)"
              className={motionOK ? "draw-on" : undefined}
            />
          </>
        ) : null}

        {/* The planet. Bloom, atmosphere, sphere, rolling land, terminator. */}
        <circle cx={C} cy={C} r={PLANET_R + 46} fill="url(#od-bloom)" />
        <circle cx={C} cy={C} r={PLANET_R + 7} fill="url(#od-atmo)" />
        <circle cx={C} cy={C} r={PLANET_R} fill="url(#od-globe)" />
        <g clipPath="url(#od-clip)">
          <g
            style={{
              animation: "roll 220s linear infinite",
              transformBox: "view-box",
            }}
          >
            {[0, 1].map((copy) =>
              LAND.map(([x, y, rx, ry, fill], i) => (
                <ellipse
                  key={`${copy}-${i}`}
                  cx={x + copy * 224}
                  cy={y}
                  rx={rx}
                  ry={ry}
                  fill={fill}
                  opacity={0.58}
                  filter="url(#od-soft)"
                />
              )),
            )}
          </g>
          {/* Polar caps do not travel with the surface. */}
          <ellipse cx={C} cy={C - PLANET_R + 12} rx={56} ry={16} fill="var(--ice)" opacity={0.22} filter="url(#od-soft)" />
          <ellipse cx={C} cy={C + PLANET_R - 10} rx={48} ry={14} fill="var(--ice)" opacity={0.16} filter="url(#od-soft)" />
          <circle cx={C} cy={C} r={PLANET_R} fill="url(#od-terminator)" />
          <ellipse
            cx={C - 40}
            cy={C - 46}
            rx={44}
            ry={24}
            fill="#fff"
            opacity={0.1}
            filter="url(#od-soft)"
            transform={`rotate(-24 ${C - 40} ${C - 46})`}
          />
        </g>
        <circle cx={C} cy={C} r={PLANET_R} fill="none" stroke="var(--atmo)" strokeOpacity="0.4" strokeWidth={1} />

        {/* Tasks, at their hour and at the curve's radius. */}
        {mine.map((task) => {
          const h = hoursSince(windowStart, task.scheduled);
          const [x, y] = point(h, radiusFor(task.predicted_alertness));
          const tone = task.raises_situation ? toneOf(task.risk_level) : "ok";
          const color = TONE_VAR[tone];
          const selected = !!task.situation_id && task.situation_id === selectedSituation;
          const clickable = !!task.situation_id;
          return (
            <g
              key={task.task_id}
              role={clickable ? "button" : undefined}
              tabIndex={clickable ? 0 : undefined}
              aria-label={`${task.label} at ${utcTime(task.scheduled)}, predicted alertness ${task.predicted_alertness.toFixed(2)}, ${task.criticality} criticality`}
              className={clsx(clickable ? "cursor-pointer" : "cursor-default")}
              onClick={() => clickable && onSelectSituation(task.situation_id as string)}
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
              <circle cx={x} cy={y} r={px(17)} fill="transparent" />
              {task.raises_situation ? (
                <circle
                  cx={x}
                  cy={y}
                  r={px(12)}
                  fill={color}
                  opacity={0.22}
                  className={selected ? "breathe" : undefined}
                  style={{ transformOrigin: `${x}px ${y}px`, transformBox: "view-box" }}
                />
              ) : null}
              <circle
                cx={x}
                cy={y}
                r={selected ? px(7.5) : px(5.5)}
                fill={selected ? color : "var(--void-deep)"}
                stroke={color}
                strokeWidth={px(selected ? 2 : 2.2)}
                style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: "r .3s ease" }}
              />
            </g>
          );
        })}
      </svg>

      {/* What the pointer is on. Positioned in per cent of a square container,
          which is exactly how the SVG places the mark it belongs to — so the
          label tracks the node at every width without measuring anything. */}
      {mine.map((task) => {
        if (task.task_id !== hovered) return null;
        const h = hoursSince(windowStart, task.scheduled);
        const [x, y] = point(h, radiusFor(task.predicted_alertness));
        return (
          <div
            key={task.task_id}
            role="tooltip"
            className="glass-3 rise pointer-events-none absolute z-10 w-max max-w-[190px] rounded-[var(--radius-xs)] px-2.5 py-2"
            style={{
              left: `${(x / SIZE) * 100}%`,
              top: `${(y / SIZE) * 100}%`,
              transform: "translate(-50%, calc(-100% - 14px))",
              background: "color-mix(in oklab, var(--void-deep) 92%, transparent)",
              backdropFilter: "blur(14px)",
            }}
          >
            <div className="mono text-[11px] text-[var(--ink-3)]">
              {utcTime(task.scheduled)} · {task.criticality}
            </div>
            <div className="mt-1 text-[12px] leading-snug text-[var(--ink)]">{task.label}</div>
            <div className="readout mt-1 text-[12px]" style={{ color: TONE_VAR[task.raises_situation ? toneOf(task.risk_level) : "ok"] }}>
              {task.predicted_alertness.toFixed(2)} predicted
            </div>
          </div>
        );
      })}

      {/* The centre reads as part of the planet, so it is HTML rather than SVG
          text: real font metrics, real ellipsis, real selection. */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className="max-w-[52%] text-center">
          {flagged ? (
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
              <div className="mt-2 flex justify-center">
                <Chip tone={flagged.raises_situation ? toneOf(flagged.risk_level) : "ok"} solid>
                  {flagged.raises_situation ? flagged.risk_level : "cleared"}
                </Chip>
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
    </div>
  );
}

/** The dial's key. Small, and beside the dial rather than over it. */
export function OrbitLegend({ className }: { className?: string }) {
  const items: [string, string, string | null][] = [
    ["var(--info)", "Predicted alertness", null],
    ["var(--warn)", "Execution threshold", "0.70"],
    ["var(--bad)", "Circadian low", null],
    ["var(--iris)", "Scheduled sleep", null],
  ];
  return (
    <ul className={clsx("flex flex-wrap items-center gap-x-5 gap-y-2", className)}>
      {items.map(([color, label, note]) => (
        <li key={label} className="flex items-center gap-2 text-[12px] text-[var(--ink-2)]">
          <span
            className="h-[3px] w-5 shrink-0 rounded-full"
            style={{ background: color, boxShadow: `0 0 8px -1px ${color}` }}
          />
          {label}
          {note ? <span className="readout text-[11px] text-[var(--ink-3)]">{note}</span> : null}
        </li>
      ))}
    </ul>
  );
}
