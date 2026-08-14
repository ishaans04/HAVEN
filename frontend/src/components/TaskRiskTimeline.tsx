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
import { Panel, Tag, utcTime } from "./ui";

const CHART_HEIGHT = 210;

const CRIT_TONE: Record<string, "bad" | "warn" | "neutral"> = {
  high: "bad",
  medium: "warn",
  low: "neutral",
};

/** Contiguous runs of a boolean flag along the curve, as [startHour, endHour]. */
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
 * Zone 2 — Task-Risk Timeline.
 *
 * Upcoming critical tasks plotted directly against predicted alertness, with
 * circadian lows marked. The point of the zone is that a collision is visible
 * before it arrives, not after.
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
    return (
      <Panel zone="Zone 2" title="Task-Risk Timeline">
        <div className="p-6 text-[12px] text-[var(--hv-muted)]">Select a crew member.</div>
      </Panel>
    );
  }

  const start = new Date(windowStart).getTime();
  const hoursFrom = (iso: string) => (new Date(iso).getTime() - start) / 3_600_000;

  const data = crew.curve.map((p) => ({
    t: hoursFrom(p.at),
    score: p.score,
    kss: p.kss,
    asleep: p.asleep,
    low: p.in_circadian_low,
    label: utcTime(p.at),
  }));

  const circadianBands = runs(data.map((d) => ({ t: d.t, flag: d.low })));
  const sleepBands = runs(data.map((d) => ({ t: d.t, flag: d.asleep })));
  const crewTasks = tasks.filter((t) => t.assigned_to === crew.crew_member);

  return (
    <Panel
      zone="Zone 2"
      title={`Task-Risk Timeline — ${crew.name}`}
      hint="Predicted alertness across the evaluation window. Shaded bands are circadian lows; hatched blocks are scheduled sleep."
      right={
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Tag tone="info">24 h window</Tag>
          <span className="mono text-[10px] text-[var(--hv-dim)]">
            {crewTasks.length} task{crewTasks.length === 1 ? "" : "s"} assigned
          </span>
        </div>
      }
    >
      <div ref={chartRef} className="w-full px-2 pt-3" style={{ height: CHART_HEIGHT + 12 }}>
        {chartWidth > 0 ? (
          <AreaChart
            width={chartWidth}
            height={CHART_HEIGHT}
            data={data}
            margin={{ top: 16, right: 16, bottom: 4, left: -18 }}
          >
            <defs>
              <linearGradient id="alertFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4aa8ff" stopOpacity={0.42} />
                <stop offset="100%" stopColor="#4aa8ff" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke="#1e2733" strokeDasharray="2 4" vertical={false} />

            {sleepBands.map(([a, b], i) => (
              <ReferenceArea key={`s${i}`} x1={a} x2={b} fill="#a78bfa" fillOpacity={0.08} />
            ))}
            {circadianBands.map(([a, b], i) => (
              <ReferenceArea key={`c${i}`} x1={a} x2={b} fill="#ff6b5e" fillOpacity={0.1} />
            ))}

            <XAxis
              dataKey="t"
              type="number"
              domain={[0, 24]}
              ticks={[0, 4, 8, 12, 16, 20, 24]}
              tickFormatter={(h: number) => `${String(h % 24).padStart(2, "0")}:00`}
              stroke="#5b6b7f"
              tick={{ fontSize: 10 }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.7, 1]}
              stroke="#5b6b7f"
              tick={{ fontSize: 10 }}
              tickLine={false}
              width={44}
            />

            <ReferenceLine
              y={0.7}
              stroke="#f2c14e"
              strokeDasharray="4 3"
              label={{
                value: "execution threshold",
                position: "insideTopRight",
                fill: "#f2c14e",
                fontSize: 9,
              }}
            />

            <Tooltip
              contentStyle={{
                background: "#0e131b",
                border: "1px solid #2b3746",
                borderRadius: 8,
                fontSize: 11,
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
              stroke="#4aa8ff"
              strokeWidth={2}
              fill="url(#alertFill)"
              isAnimationActive={false}
            />

            {crewTasks.map((task) => (
              <ReferenceDot
                key={task.task_id}
                x={hoursFrom(task.scheduled)}
                y={task.predicted_alertness}
                r={5}
                fill={
                  task.risk_level === "critical"
                    ? "#ff4d4d"
                    : task.risk_level === "elevated"
                      ? "#f2c14e"
                      : "#35d6a4"
                }
                stroke="#070a0f"
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        ) : null}
      </div>

      <ul className="divide-y divide-[var(--hv-line)] border-t border-[var(--hv-line)]">
        {tasks.map((task) => {
          const selected = task.situation_id === selectedSituation;
          const mine = task.assigned_to === crew.crew_member;
          return (
            <li key={task.task_id}>
              <button
                disabled={!task.situation_id}
                onClick={() => task.situation_id && onSelectSituation(task.situation_id)}
                className={clsx(
                  "flex w-full items-center gap-3 px-4 py-2 text-left",
                  selected && "bg-[var(--hv-panel-raised)]",
                  task.situation_id
                    ? "hover:bg-[var(--hv-panel-raised)]/60"
                    : "cursor-default opacity-55",
                )}
              >
                <span className="mono w-12 shrink-0 text-[11px] text-[var(--hv-muted)]">
                  {utcTime(task.scheduled)}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={clsx(
                      "block truncate text-[12px]",
                      mine ? "text-[var(--hv-text)]" : "text-[var(--hv-muted)]",
                    )}
                  >
                    {task.label}
                  </span>
                  <span className="mono text-[10px] text-[var(--hv-dim)]">
                    {task.task_id} · {task.assigned_name} · predicted{" "}
                    {task.predicted_alertness.toFixed(2)}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {task.circadian_low ? <Tag tone="bad">circadian low</Tag> : null}
                  <Tag tone={CRIT_TONE[task.criticality]}>{task.criticality}</Tag>
                  {task.raises_situation ? (
                    <Tag tone={task.risk_level === "critical" ? "bad" : "warn"}>
                      {task.risk_level}
                    </Tag>
                  ) : (
                    <Tag tone="good">archived</Tag>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
