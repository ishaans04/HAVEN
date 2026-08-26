"use client";

import { useState } from "react";
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
  /** One per precondition, in the order the checker tested them. */
  flags: boolean[];
  why: string | null;
}

/** Trim to a whole word. Cutting mid-word reads as a rendering fault. */
function clip(text: string, max: number) {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).trimEnd()}…`;
}

const W = 820;
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
  /**
   * Which lane the reader is on.
   *
   * Four lanes of near-identical wording is exactly the situation the corpus
   * was built to create, so telling them apart is the work. Holding one dims
   * the rest, which is the cheapest way to isolate a row in a diagram that
   * cannot use whitespace to separate them.
   */
  const [held, setHeld] = useState<string | null>(null);

  if (!lanes.length) return null;

  const height = TOP + lanes.length * LANE_GAP + 34;
  const survivorIndex = lanes.findIndex((l) => l.admissible);
  const laneY = (i: number) => TOP + i * LANE_GAP;
  // Level with whichever lane survived, so the citation cannot read as
  // belonging to a passage that was rejected.
  const exitY = survivorIndex >= 0 ? laneY(survivorIndex) : height / 2 + 6;

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
            fontSize="11"
            letterSpacing="1.5"
          >
            RETRIEVED {lanes.length}
          </text>
          <text
            x={GATE_X - 12}
            y="13"
            fill="var(--warn)"
            className="mono"
            fontSize="11"
            letterSpacing="1.5"
          >
            CHECKER
          </text>
          <text
            x={W - 4}
            y="13"
            fill={survivorIndex >= 0 ? "var(--ok)" : "var(--bad)"}
            className="mono"
            fontSize="11"
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
                  d={`M ${LEFT} ${y} L ${GATE_X} ${y} C ${GATE_X + 96} ${y} ${GATE_X + 118} ${exitY} ${W - 130} ${exitY} L ${W - 44} ${exitY}`}
                  fill="none"
                  stroke="url(#fn-pass)"
                  strokeWidth="3"
                  strokeLinecap="round"
                />
              );
            }
            // Rejected lanes peel away downward and fade out.
            const drop = 16 + i * 4;
            return (
              <path
                key={lane.passageId}
                d={`M ${LEFT} ${y} L ${GATE_X} ${y} C ${GATE_X + 26} ${y} ${GATE_X + 34} ${y + drop * 0.6} ${GATE_X + 46} ${y + drop}`}
                fill="none"
                stroke="url(#fn-rej)"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
            );
          })}

          {/* Lane identities, the tally that decided each one, and which of
              its conditions the checker actually failed. */}
          {lanes.map((lane, i) => {
            const y = laneY(i);
            const dim = held !== null && held !== lane.passageId;
            return (
              <g
                key={`l-${lane.passageId}`}
                tabIndex={0}
                role="button"
                aria-label={`${lane.passageId}, similarity ${lane.relevance.toFixed(3)}, ${lane.met} of ${lane.total} preconditions satisfied${lane.admissible ? ", admitted" : `, rejected${lane.why ? `: ${lane.why}` : ""}`}`}
                opacity={dim ? 0.32 : 1}
                style={{ transition: "opacity .22s ease", outline: "none" }}
                onMouseEnter={() => setHeld(lane.passageId)}
                onMouseLeave={() => setHeld((v) => (v === lane.passageId ? null : v))}
                onFocus={() => setHeld(lane.passageId)}
                onBlur={() => setHeld((v) => (v === lane.passageId ? null : v))}
              >
                {/* A hit area over the whole row: the marks themselves are
                    hairlines and 11px text, which is nothing to aim at. */}
                <rect
                  x={LEFT}
                  y={y - 22}
                  width={W - LEFT * 2}
                  height={LANE_GAP - 6}
                  fill="transparent"
                />
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
                  fontSize="11"
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
                {/* One lamp per precondition, in the order they were tested.
                    Only the failures carry colour -- a row of green ticks
                    beside a row of red ones spends the reader's attention on
                    the conditions that were fine. */}
                {lane.flags.map((ok, c) => (
                  <circle
                    key={c}
                    cx={GATE_X + 50 + c * 11}
                    cy={y - 13}
                    r={3.4}
                    fill={ok ? "color-mix(in oklab, var(--ok) 42%, transparent)" : "var(--bad)"}
                  />
                ))}

                {!lane.admissible && lane.why ? (
                  <text x={GATE_X + 116} y={y - 9} fill="var(--ink-3)" fontSize="11">
                    {clip(lane.why, 78)}
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
                fontSize="11"
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
