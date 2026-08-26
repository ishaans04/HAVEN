"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import clsx from "clsx";
import type { CrewReadiness, TimelineTask } from "@/lib/types";
import { useElementWidth } from "@/lib/useElementWidth";
import { Chip, TONE_VAR, toneOf, utcTime } from "./ui";

const CHART_HEIGHT = 220;

/** Contiguous runs of a flag along the curve, as [startHour, endHour]. */
function runs(points: { t: number; flag: boolean }[]): [number, number][] {
  const out: [number, number][] = [];
  let start: number | null = null;
  points.forEach((p, i) => {
    if (p.flag && start === null) start = p.t;
    const ending = !p.flag || i === points.length - 1;
    if (start !== null && ending) {
      out.push([start, p.t]);
      start = null;
    }
  });
  return out;
}

/**
 * The dial's readings, as a line.
 *
 * The dial above answers "is a hard task landing in a bad hour". This answers
 * "what exactly is the number at 04:20", which is a different question with a
 * different right instrument. Both are the same curve; only one of them needs
 * to be on screen before you ask.
 */
export function TaskRiskTimeline({
  crew,
  tasks,
  windowStart,
  onSelectSituation,
  selectedSituation,
}: {
  crew: CrewReadiness | null;
  tasks: TimelineTask[];
  windowStart: string;
  onSelectSituation: (situationId: string) => void;
  selectedSituation: string | null;
}) {
  const { ref: chartRef, width: chartWidth } = useElementWidth<HTMLDivElement>();

  if (!crew) {
    return <p className="px-1 text-[13px] text-[var(--ink-2)]">Select a crew member.</p>;
  }

  const start = new Date(windowStart).getTime();
  const hoursFrom = (iso: string) => (new Date(iso).getTime() - start) / 3_600_000;

  const data = crew.curve.map((p) => ({
    t: hoursFrom(p.at),
    score: p.score,
    kss: p.kss,
    asleep: p.asleep,
    low: p.in_circadian_low,
  }));

  const circadianBands = runs(data.map((d) => ({ t: d.t, flag: d.low })));
  const sleepBands = runs(data.map((d) => ({ t: d.t, flag: d.asleep })));
  const crewTasks = tasks.filter((t) => t.assigned_to === crew.crew_member);

  return (
    <div>
      <div className="pb-1">
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 px-2">
          <span className="text-[13px] text-[var(--ink-2)]">
            Predicted alertness · {crew.name}
          </span>
          <span className="mono text-[11px] text-[var(--ink-3)]">
            {crewTasks.length} task{crewTasks.length === 1 ? "" : "s"} assigned · 24 h window
          </span>
        </div>
        <div ref={chartRef} className="w-full" style={{ height: CHART_HEIGHT + 8 }}>
          {chartWidth > 0 ? (
            <AreaChart
              width={chartWidth}
              height={CHART_HEIGHT}
              data={data}
              margin={{ top: 16, right: 14, bottom: 4, left: -14 }}
            >
              <defs>
                <linearGradient id="tl-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--info)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--info)" stopOpacity={0.01} />
                </linearGradient>
              </defs>

              <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="2 5" vertical={false} />

              {sleepBands.map(([a, b], i) => (
                <ReferenceArea key={`s${i}`} x1={a} x2={b} fill="var(--accent)" fillOpacity={0.09} />
              ))}
              {circadianBands.map(([a, b], i) => (
                <ReferenceArea key={`c${i}`} x1={a} x2={b} fill="var(--bad)" fillOpacity={0.1} />
              ))}

              <XAxis
                dataKey="t"
                type="number"
                domain={[0, 24]}
                ticks={[0, 4, 8, 12, 16, 20, 24]}
                tickFormatter={(h: number) => `${String(h % 24).padStart(2, "0")}:00`}
                stroke="rgba(255,255,255,0.2)"
                tick={{ fontSize: 11, fill: "var(--ink-3)" }}
                tickLine={false}
                // At the origin the first hour label and the y-axis zero were
                // overlapping by a couple of pixels -- the default puts both
                // tight into the corner. A little margin on each axis pushes
                // them apart without moving the plot itself.
                tickMargin={8}
              />
              <YAxis
                domain={[0, 1]}
                ticks={[0, 0.25, 0.5, 0.7, 1]}
                stroke="rgba(255,255,255,0.2)"
                tick={{ fontSize: 11, fill: "var(--ink-3)" }}
                tickLine={false}
                tickMargin={6}
                // Room for the labels *and* the margin: at 46 the tick margin
                // pushed "0.25" three pixels off the left edge of the chart.
                width={56}
              />

              <ReferenceLine
                y={0.7}
                stroke="var(--warn)"
                strokeDasharray="4 4"
                strokeOpacity={0.8}
                label={{
                  value: "execution threshold",
                  position: "insideTopRight",
                  fill: "var(--warn)",
                  fontSize: 11,
                }}
              />

              <Tooltip
                contentStyle={{
                  background: "rgba(12,10,28,0.92)",
                  border: "1px solid rgba(255,255,255,0.14)",
                  borderRadius: 12,
                  fontSize: 12,
                  backdropFilter: "blur(12px)",
                }}
                labelFormatter={(h) =>
                  `${String(Math.floor(Number(h))).padStart(2, "0")}:${String(
                    Math.round((Number(h) % 1) * 60),
                  ).padStart(2, "0")}Z`
                }
                formatter={(value, name) => [
                  typeof value === "number" ? value.toFixed(3) : String(value),
                  name === "score" ? "alertness" : String(name),
                ]}
              />

              <Area
                type="monotone"
                dataKey="score"
                stroke="var(--info)"
                strokeWidth={2}
                fill="url(#tl-fill)"
                isAnimationActive={false}
              />

              {crewTasks.map((task) => (
                <ReferenceDot
                  key={task.task_id}
                  x={hoursFrom(task.scheduled)}
                  y={task.predicted_alertness}
                  r={5}
                  fill={TONE_VAR[task.raises_situation ? toneOf(task.risk_level) : "ok"]}
                  stroke="var(--void-deep)"
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          ) : null}
        </div>
      </div>

      <ul className="mt-2 space-y-2">
        {tasks.map((task) => {
          const selected = task.situation_id === selectedSituation;
          const mine = task.assigned_to === crew.crew_member;
          return (
            <li key={task.task_id}>
              <button
                disabled={!task.situation_id}
                aria-pressed={task.situation_id ? selected : undefined}
                onClick={() => task.situation_id && onSelectSituation(task.situation_id)}
                className={clsx(
                  "flex w-full items-center gap-3 rounded-[var(--radius-sm)] px-4 py-2.5 text-left",
                  task.situation_id ? "selectable" : "glass-2 cursor-default opacity-60",
                )}
              >
                <span className="mono w-14 shrink-0 text-[12px] text-[var(--ink-2)]">
                  {utcTime(task.scheduled)}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={clsx(
                      "block truncate text-[13px]",
                      mine ? "text-[var(--ink)]" : "text-[var(--ink-2)]",
                    )}
                  >
                    {task.label}
                  </span>
                  <span className="mono text-[11px] text-[var(--ink-3)]">
                    {task.task_id} · {task.assigned_name} · predicted{" "}
                    {task.predicted_alertness.toFixed(2)}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {task.circadian_low ? <Chip tone="bad">body-clock low</Chip> : null}
                  <Chip tone={toneOf(task.criticality)}>{task.criticality}</Chip>
                  {task.raises_situation ? (
                    <Chip tone={toneOf(task.risk_level)} solid>
                      {task.risk_level}
                    </Chip>
                  ) : (
                    <Chip tone="ok">cleared</Chip>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
