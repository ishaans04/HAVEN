"use client";

import type { Citation } from "@/lib/types";

/**
 * How four candidate rules became one citation.
 *
 * This replaced four tiles that between them spent forty-six words *describing*
 * what the architecture did. Drawn, it demonstrates it instead: lanes come in
 * from the retrieval tier, a deterministic gate throws most of them out with
 * the clause tally that killed each one, and whatever survives arrives as the
 * citation on the card above.
 *
 * The detail worth the whole diagram is the top lane. On this corpus the
 * governing passage scores a perfect 1.000 on retrieval similarity — and so
 * would a near-miss that shares its vocabulary, which is exactly what the
 * near-misses are built to do. Similarity gets you into the candidate set and
 * buys nothing after that. Seeing a 0.984 lane die at the gate says that in a
 * way no sentence has managed.
 *
 * Geometry is computed from the candidate list rather than hard-coded, so the
 * picture is right for three candidates or for eight, and right when every one
 * of them fails.
 */

interface Lane {
  passageId: string;
  relevance: number;
  admissible: boolean;
  met: number;
  total: number;
  why: string | null;
}

const W = 720;
const LANE_GAP = 46;
const TOP = 40;
const GATE_X = 300;
const LEFT = 6;

export function RetrievalFunnel({
  lanes,
  citation,
  className,
}: {
  lanes: Lane[];
  citation: Citation | null | undefined;
  className?: string;
}) {
  if (!lanes.length) return null;

  const height = TOP + lanes.length * LANE_GAP + 34;
  const survivorIndex = lanes.findIndex((l) => l.admissible);
  const exitY = height / 2 + 6;
  const laneY = (i: number) => TOP + i * LANE_GAP;

  return (
    <div className={className}>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${height}`}
          width={W}
          className="w-full min-w-[520px]"
          role="img"
          aria-label={
            `${lanes.length} passages were retrieved. ` +
            lanes
              .map((l) =>
                l.admissible
                  ? `${l.passageId} satisfied ${l.met} of ${l.total} preconditions and was admitted.`
                  : `${l.passageId} satisfied ${l.met} of ${l.total} and was rejected${l.why ? `: ${l.why}` : ""}.`,
              )
              .join(" ") +
            (citation ? ` The citation is ${citation.doc} section ${citation.section}.` : "")
          }
        >
          <defs>
            <linearGradient id="fn-rej" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--bad)" stopOpacity="0.5" />
              <stop offset="55%" stopColor="var(--bad)" stopOpacity="0.34" />
              <stop offset="100%" stopColor="var(--bad)" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="fn-pass" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--ok)" stopOpacity="0.45" />
              <stop offset="100%" stopColor="var(--ok)" stopOpacity="1" />
            </linearGradient>
          </defs>

          {/* Stage headings. */}
          <text
            x={LEFT}
            y="13"
            fill="var(--ink-3)"
            className="mono"
            fontSize="10.5"
            letterSpacing="1.5"
          >
            RETRIEVED {lanes.length}
          </text>
          <text
            x={GATE_X - 12}
            y="13"
            fill="var(--warn)"
            className="mono"
            fontSize="10.5"
            letterSpacing="1.5"
          >
            CHECKER
          </text>
          <text
            x={W - 4}
            y="13"
            fill={survivorIndex >= 0 ? "var(--ok)" : "var(--bad)"}
            className="mono"
            fontSize="10.5"
            letterSpacing="1.5"
            textAnchor="end"
          >
            {survivorIndex >= 0 ? "CITED 1" : "NONE APPLIED"}
          </text>

          {/* The gate itself. */}
          <line
            x1={GATE_X}
            y1="24"
            x2={GATE_X}
            y2={height - 16}
            stroke="var(--warn)"
            strokeOpacity="0.45"
            strokeWidth="1.5"
            strokeDasharray="3 5"
          />

          {lanes.map((lane, i) => {
            const y = laneY(i);
            if (lane.admissible) {
              return (
                <path
                  key={lane.passageId}
                  d={`M ${LEFT} ${y} L ${GATE_X} ${y} C ${GATE_X + 96} ${y} ${GATE_X + 118} ${exitY} ${W - 130} ${exitY} L ${W - 26} ${exitY}`}
                  fill="none"
                  stroke="url(#fn-pass)"
                  strokeWidth="3"
                  strokeLinecap="round"
                />
              );
            }
            // Rejected lanes peel away downward and fade out.
            const drop = 20 + i * 6;
            return (
              <path
                key={lane.passageId}
                d={`M ${LEFT} ${y} L ${GATE_X} ${y} C ${GATE_X + 54} ${y} ${GATE_X + 70} ${y + drop * 0.6} ${GATE_X + 104} ${y + drop}`}
                fill="none"
                stroke="url(#fn-rej)"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
            );
          })}

          {/* Lane identities and the tally that decided each one. */}
          {lanes.map((lane, i) => {
            const y = laneY(i);
            return (
              <g key={`l-${lane.passageId}`}>
                <text
                  x={LEFT + 2}
                  y={y - 9}
                  fill={lane.admissible ? "var(--ink)" : "var(--ink-2)"}
                  className="mono"
                  fontSize="11"
                >
                  {lane.passageId}
                </text>
                <text
                  x={LEFT + 92}
                  y={y - 9}
                  fill="var(--ink-3)"
                  className="mono"
                  fontSize="10"
                >
                  sim {lane.relevance.toFixed(3)}
                </text>
                <text
                  x={GATE_X + 14}
                  y={y - 5}
                  fill={lane.admissible ? "var(--ok)" : "var(--bad)"}
                  className="mono"
                  fontSize="11"
                >
                  {lane.met}/{lane.total}
                </text>
                {!lane.admissible && lane.why ? (
                  <text
                    x={GATE_X + 112}
                    y={y + 20 + i * 6}
                    fill="var(--ink-3)"
                    fontSize="10.5"
                  >
                    {lane.why.length > 46 ? `${lane.why.slice(0, 44)}…` : lane.why}
                  </text>
                ) : null}
              </g>
            );
          })}

          {/* Where the survivor lands. */}
          {survivorIndex >= 0 && citation ? (
            <g>
              <circle cx={W - 26} cy={exitY} r="13" fill="var(--ok)" opacity="0.18" />
              <circle cx={W - 26} cy={exitY} r="6.5" fill="var(--ok)" />
              <text
                x={W - 42}
                y={exitY - 12}
                fill="var(--ok)"
                textAnchor="end"
                className="mono"
                fontSize="11"
              >
                {citation.doc} §{citation.section}
              </text>
              <text
                x={W - 42}
                y={exitY + 14}
                fill="var(--ink-3)"
                textAnchor="end"
                fontSize="10.5"
              >
                verified clause by clause
              </text>
            </g>
          ) : null}
        </svg>
      </div>
    </div>
  );
}
