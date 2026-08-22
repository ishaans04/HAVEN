"use client";

import { Clock3, Gauge, MoonStar } from "lucide-react";
import type { Situation } from "@/lib/types";
import { Label, TONE_VAR } from "./ui";

/**
 * The four figures, as one reading.
 *
 * They were four equal boxes, which gave the KSS footnote the same weight as
 * the only fact that decides anything: alertness sits at 0.69 against a line of
 * 0.70. Equal weight is a claim, and it was the wrong one.
 *
 * So alertness gets the track, with the threshold drawn on it. You can see the
 * miss without reading a digit, which is the whole point for a reader meeting
 * this screen for the first time. Workload, hours awake and the body clock keep
 * their numbers and lose their captions to the three small gauges beside it.
 */
export function Vitals({ situation }: { situation: Situation }) {
  const score = situation.alertness_score;
  const threshold = situation.recommendation?.projection?.threshold ?? 0.7;
  const below = score < threshold;
  const tone = score < 0.6 ? "bad" : below ? "warn" : "ok";
  const colour = TONE_VAR[tone];
  const gap = Math.abs(threshold - score);

  return (
    <div className="glass-2 px-4 py-4">
      {/* The reading that decides. */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="readout text-[38px] leading-none" style={{ color: colour }}>
          {score.toFixed(2)}
        </span>
        <Label className="!text-[10.5px]">alertness</Label>
        <span className="ml-auto text-[12px]" style={{ color: colour }}>
          {gap < 0.005
            ? "on the line"
            : `${gap.toFixed(2)} ${below ? "below" : "above"} the line`}
        </span>
      </div>

      <div className="relative mt-3 h-2.5 rounded-full" style={{ background: "rgba(255,255,255,0.07)" }}>
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out"
          style={{
            width: `${Math.max(0, Math.min(100, score * 100))}%`,
            background: `linear-gradient(90deg, color-mix(in oklab, ${colour} 35%, transparent), ${colour})`,
            boxShadow: `0 0 14px -3px ${colour}`,
          }}
        />
        {/* The threshold, as a notch through the track rather than a line over
            it — the reading either reaches it or it does not. */}
        <div
          className="absolute -top-1.5 -bottom-1.5 w-[2px] rounded-full bg-[var(--ink)]"
          style={{ left: `${Math.min(100, threshold * 100)}%` }}
        />
        <span
          className="mono absolute -top-[22px] whitespace-nowrap text-[10px] text-[var(--ink-2)]"
          style={{ left: `${Math.min(100, threshold * 100)}%`, transform: "translateX(-50%)" }}
        >
          {threshold.toFixed(2)} execution threshold
        </span>
      </div>

      {/* Everything else, at the size it deserves. */}
      <div className="mt-4 grid grid-cols-3 gap-2">
        <MiniGauge
          icon={<Gauge size={13} />}
          value={situation.workload_score.toFixed(0)}
          label="workload"
          fraction={situation.workload_score / 100}
          colour="var(--info)"
          title={`NASA-TLX ${situation.workload_score.toFixed(1)}, ${situation.evidence.workload_band.replace(/_/g, " ")}`}
        />
        <MiniGauge
          icon={<Clock3 size={13} />}
          value={`${situation.evidence.hours_awake.toFixed(1)}h`}
          label="awake"
          fraction={Math.min(1, situation.evidence.hours_awake / 18)}
          colour={situation.evidence.hours_awake > 12 ? "var(--warn)" : "var(--ok)"}
          title={`Sleep debt ${situation.evidence.sleep_debt_h.toFixed(1)} hours`}
        />
        <MiniGauge
          icon={<MoonStar size={13} />}
          value={situation.circadian_flag ? "Trough" : "Clear"}
          label="body clock"
          fraction={situation.circadian_flag ? 1 : 0.18}
          colour={situation.circadian_flag ? "var(--bad)" : "var(--ok)"}
          title={`Karolinska sleepiness ${situation.evidence.kss.toFixed(1)}`}
        />
      </div>
    </div>
  );
}

function MiniGauge({
  icon,
  value,
  label,
  fraction,
  colour,
  title,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  fraction: number;
  colour: string;
  title: string;
}) {
  const r = 12;
  const c = 2 * Math.PI * r;
  return (
    <div
      className="flex items-center gap-2.5 rounded-[var(--radius-xs)] px-2.5 py-2"
      style={{ background: "rgba(255,255,255,0.04)" }}
      title={title}
    >
      <span className="relative inline-flex h-[30px] w-[30px] shrink-0 items-center justify-center">
        <svg width="30" height="30" className="-rotate-90" aria-hidden>
          <circle cx="15" cy="15" r={r} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="2.5" />
          <circle
            cx="15"
            cy="15"
            r={r}
            fill="none"
            stroke={colour}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - Math.max(0, Math.min(1, fraction)))}
          />
        </svg>
        <span className="absolute" style={{ color: colour }}>
          {icon}
        </span>
      </span>
      <span className="min-w-0">
        <span className="readout block truncate text-[14px] leading-none text-[var(--ink)]">
          {value}
        </span>
        <span className="mt-1 block text-[9.5px] uppercase tracking-[0.12em] text-[var(--ink-3)]">
          {label}
        </span>
      </span>
      <span className="sr-only">{title}</span>
    </div>
  );
}
