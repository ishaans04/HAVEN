"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  ArrowRight,
  Calculator,
  ClipboardList,
  Clock4,
  Compass,
  FileSearch,
  Gauge,
  Layers,
  ShieldAlert,
  UserCheck,
  Users,
} from "lucide-react";
import { useParallax } from "@/lib/motion";
import { PlanetLimb } from "./PlanetLimb";
import { StarField } from "./StarField";
import { Chip, GlassCard, Label, Reveal } from "./ui";

/**
 * The front door.
 *
 * The console is an instrument, and an instrument does not explain itself — it
 * assumes you already know what you are holding. That is fine for the operator
 * it was designed for and useless for everyone who arrives at a URL: a judge, a
 * reviewer, somebody sent a link. This page is the twenty seconds before the
 * instrument.
 *
 * Its claims are deliberately the same claims the product makes about itself,
 * in the same plain language, including the ones that are limitations. A
 * landing page that oversells a system whose entire argument is "it refuses
 * when it does not know" would undo the argument on the way in.
 */
export function Landing() {
  return (
    <>
      <StarField />

      <main>
        <Hero />
        <Problem />
        <GoldenRule />
        <Pipeline />
        <Layout />
        <Honesty />
        <Close />
      </main>
    </>
  );
}

/* -------------------------------------------------------------------------- */

function Hero() {
  const { ref, layer } = useParallax<HTMLElement>();

  return (
    <section
      ref={ref}
      className="relative isolate flex min-h-[92vh] flex-col justify-center overflow-hidden px-5 pb-32 pt-24 sm:px-8"
    >
      {/* The planet sits behind and below the type, cropped by the section, the
          way a window crops a view. */}
      {/* A fixed height rather than a percentage: the limb's viewBox is 2.3:1,
          and `slice` crops whatever the container does not have room for. Sized
          in pixels, the horizon lands in a predictable place at every viewport
          height instead of sliding up out of frame on a short one. */}
      {/* Both decorative layers drift; neither the type nor the buttons do.
          Content that slides under the cursor is content you have to chase. */}
      <div
        {...layer({ scroll: 0.26, pointer: 15 })}
        className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-[560px] will-change-transform"
      >
        <PlanetLimb className="h-full w-full" />
      </div>

      {/* A scrim weighted to the side the type sits on. Without it the limb's
          hairline crosses the headline on a narrow screen — which reads as an
          accident rather than as a horizon. Painted after the limb so it lands
          over it at the same depth, and falling to nothing well before the far
          edge so the rim stays visible where there is no text. */}
      <div
        {...layer({ scroll: 0.14 })}
        className="pointer-events-none absolute inset-0 -z-10 will-change-transform"
        style={{
          background:
            "linear-gradient(102deg, color-mix(in oklab, var(--void-deep) 88%, transparent) 0%, color-mix(in oklab, var(--void-deep) 62%, transparent) 38%, color-mix(in oklab, var(--void-deep) 10%, transparent) 66%, color-mix(in oklab, var(--void-deep) 0%, transparent) 80%)",
        }}
      />

      <div className="mx-auto w-full max-w-[1560px]">
        <div className="max-w-3xl">
          <Reveal className="flex flex-wrap items-center gap-2">
            <Chip tone="accent">IBM AI Builders Challenge</Chip>
            <Chip tone="neutral">Space exploration</Chip>
          </Reveal>

          <Reveal delay={90}>
            <h1 className="display mt-7 text-[clamp(2.75rem,7.4vw,6.25rem)]">
              <span className="em block">Fatigue-aware</span>
              <span className="block text-[var(--ink-2)]">safety co-pilot</span>
            </h1>
          </Reveal>

          <Reveal delay={180}>
            <p className="mt-7 max-w-xl text-[16px] leading-relaxed text-[var(--ink-2)] sm:text-[16px]">
              A tired operator and an irreversible task are about to meet. HAVEN sees the
              collision coming, and finds the rule in the mission&rsquo;s own procedures that
              governs it. Then it hands a human the decision. When no rule fits, it says so
              instead of guessing.
            </p>
          </Reveal>

          <Reveal delay={270} className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/console/"
              className="glass-interactive group inline-flex items-center gap-2 rounded-full px-6 py-4 text-[14px] font-medium"
              style={{
                color: "var(--accent)",
                background: "color-mix(in oklab, var(--accent) 18%, transparent)",
                boxShadow:
                  "inset 0 0 0 1px color-mix(in oklab, var(--accent) 48%, transparent), 0 20px 50px -22px color-mix(in oklab, var(--accent) 70%, transparent)",
              }}
            >
              Enter the console
              <ArrowRight
                size={16}
                className="transition-transform duration-300 group-hover:translate-x-1"
              />
            </Link>
            <a
              href="#how"
              className="glass-3 glass-interactive inline-flex items-center gap-2 rounded-full px-5 py-4 text-[14px] text-[var(--ink-2)] hover:text-[var(--ink)]"
            >
              How it works
            </a>
          </Reveal>

          <Reveal delay={360}>
            <ul className="mt-12 flex flex-wrap gap-x-8 gap-y-3">
            {[
              ["Every number is arithmetic", "var(--ok)"],
              ["Every recommendation is cited", "var(--info)"],
              ["Refusal is a valid answer", "var(--accent)"],
            ].map(([text, color]) => (
              <li key={text} className="flex items-center gap-2 text-[13px] text-[var(--ink-2)]">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: color, boxShadow: `0 0 8px ${color}` }}
                />
                {text}
              </li>
            ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

const PROBLEMS: [ReactNode, string, string][] = [
  [
    <Gauge key="i" size={17} />,
    "Fatigue is invisible until it is too late",
    "A tired brain does not feel broken. Reaction time and judgement degrade measurably while the person still feels fine. Self-assessment is the one instrument here you cannot trust.",
  ],
  [
    <Users key="i" size={17} />,
    "High performers push through",
    "Astronauts are trained to power through exhaustion, and they under-report it. Partly pride, partly not wanting to be pulled off a task they trained years for. “Are you too tired for this?” is the question your best operators are least likely to answer honestly.",
  ],
  [
    <Clock4 key="i" size={17} />,
    "A tiredness number alone is noise",
    "Everyone is tired sometimes. Being tired during a rest period is fine; being tired forty minutes before a critical engine burn is not. Fatigue only means anything set against what the person is about to do.",
  ],
];

function Problem() {
  return (
    <Section
      id="how"
      label="The problem"
      title="Why this is hard to manage by hand"
      lead="On a long mission the crew performs irreversible work under chronic fatigue: a propulsive burn, a docking, a spacewalk, a hatch closeout. The radio delay back to Earth is far too long for anyone on the ground to intervene in the moment."
    >
      <div className="grid gap-3 md:grid-cols-3">
        {PROBLEMS.map(([icon, title, body], i) => (
          <Reveal key={title} delay={i * 80}>
            <GlassCard className="h-full p-6">
            <span className="glass-3 inline-flex rounded-full p-2.5 text-[var(--accent)]">{icon}</span>
            <h3 className="mt-4 text-[16px] font-medium leading-snug text-[var(--ink)]">{title}</h3>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-2)]">{body}</p>
            </GlassCard>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

function GoldenRule() {
  return (
    <Section
      label="The golden rule"
      title="The AI never produces a safety number"
      lead="Modern AI reads documents well. It also states wrong numbers with total confidence. In a system that can recommend pulling somebody off a critical task, an invented fatigue score is unacceptable, so the work is split along a hard line. That line is enforced in code, not in prompting."
    >
      <div className="grid gap-3 lg:grid-cols-2">
        <GlassCard className="p-6" live>
          <Label>The fatigue &amp; workload engine</Label>
          <h3 className="display mt-2 text-[26px]">Ordinary maths</h3>
          <p className="mt-3 text-[13px] leading-relaxed text-[var(--ink-2)]">
            Published, validated alertness and workload models. Same inputs, same score, every
            time. Checkable by hand.
          </p>
          <Owns
            owns="The alertness score, the workload score, sleep-debt, circadian phase, and every safety threshold in the system."
            question="Can it invent a number?"
            answer="No. It is arithmetic."
            tone="var(--ok)"
          />
        </GlassCard>

        <GlassCard className="p-6">
          <Label>The reasoning tier</Label>
          <h3 className="display mt-2 text-[26px]">Reading and explaining</h3>
          <p className="mt-3 text-[13px] leading-relaxed text-[var(--ink-2)]">
            Reads procedures written for humans, decides which rule governs the situation, and turns
            a bare score into a cited recommendation.
          </p>
          <Owns
            owns="Interpreting the rulebook, weighing the score against the upcoming task, drafting the briefing an operator reads."
            question="Can it invent a number?"
            answer="Yes. So it is never allowed to supply one."
            tone="var(--accent)"
          />
        </GlassCard>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {[
          [
            "Scores are calculated, never generated",
            "Every figure comes from the maths. The model is handed them already computed. It may repeat them and can never change them.",
          ],
          [
            "It flags risk, it never decides fitness",
            "No code path lets HAVEN execute, defer, or reassign anything. The output is always a recommendation or a refusal for a person to action.",
          ],
          [
            "No citation, no recommendation",
            "A recommendation without a resolvable procedure citation is invalid and never shown. The flow refuses instead.",
          ],
        ].map(([title, body], i) => (
          <Reveal key={title} delay={i * 80} className="glass-2 p-5">
            <span className="readout text-[13px] text-[var(--accent)]">
              Rule {String(i + 1).padStart(2, "0")}
            </span>
            <h4 className="mt-2 text-[14px] font-medium leading-snug text-[var(--ink)]">
              {title}
            </h4>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-3)]">{body}</p>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

function Owns({
  owns,
  question,
  answer,
  tone,
}: {
  owns: string;
  question: string;
  answer: string;
  tone: string;
}) {
  return (
    <dl className="mt-5 space-y-3.5 border-t border-white/[0.08] pt-5">
      <div>
        <dt className="label !text-[11px]">Owns</dt>
        <dd className="mt-2 text-[13px] leading-relaxed text-[var(--ink-2)]">{owns}</dd>
      </div>
      <div>
        <dt className="label !text-[11px]">{question}</dt>
        <dd className="mt-2 text-[13px] font-medium" style={{ color: tone }}>
          {answer}
        </dd>
      </div>
    </dl>
  );
}

/* -------------------------------------------------------------------------- */

const STEPS: [ReactNode, string, string][] = [
  [
    <ClipboardList key="i" size={16} />,
    "Listen",
    "Takes in recent sleep and duty history, hours on task, and how much the person is juggling. These are inputs the crew already share with flight medicine. Nothing here is hidden monitoring.",
  ],
  [
    <Calculator key="i" size={16} />,
    "Calculate",
    "Turns that history into an alertness score with published fatigue models, the same science behind airline crew scheduling. Ordinary maths, because a safety number must never be invented.",
  ],
  [
    <FileSearch key="i" size={16} />,
    "Read the manual",
    "When alertness is low, the AI searches the mission's own procedures for the rule covering the upcoming task. Then a separate check, ordinary code with no AI in it, tests whether that rule really applies.",
  ],
  [
    <UserCheck key="i" size={16} />,
    "Check the schedule",
    "Before suggesting anything, confirms the change still leaves every safety-critical role staffed by someone qualified and rested. If it cannot, it says so rather than proposing an unworkable fix.",
  ],
  [
    <ShieldAlert key="i" size={16} />,
    "Hand it to a human",
    "Produces one page: who is affected, the evidence, the task, the governing rule with its citation, and the least disruptive action. A person decides. Always.",
  ],
];

function Pipeline() {
  return (
    <Section
      label="The pipeline"
      title="Five steps. A person takes the last one."
      lead="Nothing in this sequence acts on the crew. It watches, calculates, reads, checks its own suggestion for side effects, and then stops."
    >
      <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {STEPS.map(([icon, title, body], i) => (
          <Reveal key={title} delay={i * 70} className="glass-2 relative flex flex-col p-5">
            <div className="flex items-center gap-2">
              <span
                className="inline-flex rounded-full p-2"
                style={{
                  color: i === STEPS.length - 1 ? "var(--ok)" : "var(--info)",
                  background: "rgba(255,255,255,0.06)",
                }}
              >
                {icon}
              </span>
              <span className="readout text-[12px] text-[var(--ink-3)]">
                {String(i + 1).padStart(2, "0")}
              </span>
            </div>
            <h3 className="mt-4 text-[16px] font-medium text-[var(--ink)]">{title}</h3>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-3)]">{body}</p>
          </Reveal>
        ))}
      </ol>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

function Layout() {
  const layers: [string, string, string, string][] = [
    [
      "The answer",
      "var(--accent)",
      "What to do about it",
      "The recommended action in plain language, the operator it concerns, the four figures behind it, and what the action is predicted to buy. Or a refusal, styled as a different kind of answer rather than a failure.",
    ],
    [
      "How it decided",
      "var(--info)",
      "Four counts: measured, offered, allowed, cited",
      "The whole design in four numbers. The maths went first. The search offered several candidate rules, including ones that look right and are not. A separate check threw most of them out. What survived is the rule quoted on the card above.",
    ],
    [
      "The instrument",
      "var(--ok)",
      "The whole evidence trail",
      "Every rule considered and how it was judged, condition by condition. Each step of the run and what it took. The sealed log, and every figure for every crew member. One click each. None of it was cut to keep the first read clean.",
    ],
  ];

  return (
    <Section
      label="The console"
      title="Read it in three layers"
      lead="One screen. Somebody seeing it for the first time should be able to read what is being recommended and why without opening anything. Somebody checking the decision should be able to reach every condition behind it."
    >
      <div className="grid gap-3 lg:grid-cols-3">
        {layers.map(([name, tone, headline, body], i) => (
          <Reveal key={name} delay={i * 80}>
            <GlassCard className="flex h-full flex-col p-6">
            <div className="flex items-center gap-2">
              <Layers size={15} style={{ color: tone }} />
              <span
                className="text-[11px] uppercase tracking-[0.15em]"
                style={{ color: tone }}
              >
                Layer {i + 1} · {name}
              </span>
            </div>
            <h3 className="mt-4 text-[16px] font-medium leading-snug text-[var(--ink)]">
              {headline}
            </h3>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-2)]">{body}</p>
            </GlassCard>
          </Reveal>
        ))}
      </div>

      <GlassCard className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-3 px-6 py-5">
        <Compass size={17} className="shrink-0 text-[var(--accent)]" />
        <p className="min-w-0 flex-1 text-[13px] leading-relaxed text-[var(--ink-2)]">
          First visit runs a four-stop tour of those layers, and it is replayable from the console
          masthead at any time.
        </p>
        <Link
          href="/console/"
          className="glass-3 glass-interactive inline-flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-[13px] text-[var(--ink)]"
        >
          Take the tour
          <ArrowRight size={14} />
        </Link>
      </GlassCard>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

function Honesty() {
  return (
    <Section
      label="Real vs simulated"
      title="What is real here, and what is not"
      lead="Naming limitations is part of the design here, not a disclaimer bolted onto it. This is a system whose central claim is that it flags risk honestly instead of asserting false certainty. It would be a strange thing to describe dishonestly."
    >
      <div className="grid gap-3 lg:grid-cols-2">
        <GlassCard className="p-6">
          <div className="flex items-center gap-2">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: "var(--ok)", boxShadow: "0 0 8px var(--ok)" }}
            />
            <Label>Real, and running</Label>
          </div>
          <ul className="mt-4 space-y-3 text-[13px] leading-relaxed text-[var(--ink-2)]">
            {[
              "The Three-Process Model of Alertness and NASA-TLX: the published models, computed from the inputs shown.",
              "The search across the procedure documents, with rules that look right but are not deliberately left in the results.",
              "The check that allows or rejects each rule on its own stated conditions, worked out separately from the model.",
              "Refusing, the roster and confidence checks, and the sealed log where each entry is bound to the one before it. All of it runs live on every evaluation.",
            ].map((line) => (
              <li key={line} className="flex gap-2">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[var(--ok)]" />
                {line}
              </li>
            ))}
          </ul>
        </GlassCard>

        <GlassCard className="p-6">
          <div className="flex items-center gap-2">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: "var(--warn)", boxShadow: "0 0 8px var(--warn)" }}
            />
            <Label>Simulated, and labelled as such</Label>
          </div>
          <ul className="mt-4 space-y-3 text-[13px] leading-relaxed text-[var(--ink-2)]">
            {[
              "The crew roster is representative, not real individuals.",
              "Sleep, duty and task timelines are synthetic. No public live crew-timeline feed exists.",
              "Where a rule is marked prototype, its wording follows NASA flight-rule structure but was written for this build. The console says which is which on every row.",
              "The reasoning model is a scripted Granite stand-in unless a live provider is configured, so the offline path is a first-class path rather than a degraded one.",
            ].map((line) => (
              <li key={line} className="flex gap-2">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[var(--warn)]" />
                {line}
              </li>
            ))}
          </ul>
        </GlassCard>
      </div>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

function Close() {
  return (
    <section className="relative overflow-hidden px-5 pb-24 pt-10 sm:px-8">
      <div className="mx-auto max-w-[1560px]">
        <GlassCard className="relative overflow-hidden px-6 py-14 text-center sm:px-14">
          <div
            className="pointer-events-none absolute inset-x-0 bottom-[-60%] h-[150%] -z-10"
            style={{
              background:
                "radial-gradient(60% 60% at 50% 100%, color-mix(in oklab, var(--accent) 30%, transparent), color-mix(in oklab, var(--accent) 0%, transparent) 70%)",
            }}
          />
          <h2 className="display mx-auto max-w-2xl text-[clamp(1.75rem,4vw,2.75rem)]">
            The maths owns the numbers.
            <br />
            <span className="text-[var(--ink-2)]">The human owns the decision.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-lg text-[14px] leading-relaxed text-[var(--ink-2)]">
            Eight scenarios are wired up, including the one that matters most: the situation no
            procedure governs, where the right output is to stop and escalate.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/console/"
              className="glass-interactive group inline-flex items-center gap-2 rounded-full px-6 py-4 text-[14px] font-medium"
              style={{
                color: "var(--accent)",
                background: "color-mix(in oklab, var(--accent) 18%, transparent)",
                boxShadow:
                  "inset 0 0 0 1px color-mix(in oklab, var(--accent) 48%, transparent), 0 20px 50px -22px color-mix(in oklab, var(--accent) 70%, transparent)",
              }}
            >
              Enter the console
              <ArrowRight
                size={16}
                className="transition-transform duration-300 group-hover:translate-x-1"
              />
            </Link>
            <a
              href="/docs"
              className="glass-3 glass-interactive inline-flex items-center gap-2 rounded-full px-5 py-4 text-[14px] text-[var(--ink-2)] hover:text-[var(--ink)]"
            >
              API reference
            </a>
          </div>
        </GlassCard>

        <p className="mt-8 text-center text-[12px] text-[var(--ink-3)]">
          HAVEN · Human Adaptation &amp; Vitality Enhancement Network · a prototype, and it says so
          where it is one.
        </p>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

function Section({
  id,
  label,
  title,
  lead,
  children,
}: {
  id?: string;
  label: string;
  title: string;
  lead: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-8 px-5 py-14 sm:px-8 sm:py-20">
      <div className="mx-auto max-w-[1560px]">
        <Reveal className="max-w-3xl">
          <Label>{label}</Label>
          <h2 className="display mt-3 text-[clamp(1.6rem,3.4vw,2.5rem)]">{title}</h2>
          <p className="mt-4 text-[14px] leading-relaxed text-[var(--ink-2)]">{lead}</p>
        </Reveal>
        <div className="mt-9">{children}</div>
      </div>
    </section>
  );
}
