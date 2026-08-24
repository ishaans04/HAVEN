"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight, Compass, Hand } from "lucide-react";
import { useEffect, useState } from "react";
import { useParallax } from "@/lib/motion";
import { fetchAudit, fetchEvaluation } from "@/lib/api";
import { Counterfactual, verdictFromAudit, type Verdict } from "./Counterfactual";
import { Earth } from "./Earth";
import { AlertnessGap, HardLine, LayerStack, PipelineRail } from "./LandingVisuals";
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
        <Overrule />
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
  const [sunrises, setSunrises] = useState(0);
  const [wide, setWide] = useState(true);
  const [grabbed, setGrabbed] = useState(false);
  const [bias, setBias] = useState(0);

  // The planet turns as you read down the page. Coalesced onto a frame so a
  // fast scroll cannot queue a hundred renders.
  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        setBias(window.scrollY * 0.0011);
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  // The globe is a portrait on a wide screen and a horizon on a narrow one.
  // Same sphere, different crop — nothing about the simulation changes.
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 900px)");
    const apply = () => setWide(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  return (
    <section
      ref={ref}
      className="relative isolate flex min-h-[94vh] flex-col justify-center overflow-hidden px-5 pb-28 pt-24 sm:px-8"
    >
      {/* Earth. Not a picture of Earth and not an arc standing in for one:
          a sphere lit by a sun the shader can point at, with the station's
          real 51.64-degree orbit projected through the same camera. */}
      <div
        {...layer({ scroll: 0.2, pointer: 10 })}
        className="pointer-events-none absolute inset-0 -z-10 will-change-transform"
      >
        <Earth
          className="absolute inset-0"
          placement={wide ? { cx: 0.775, cy: 0.46, r: 0.255 } : { cx: 0.5, cy: -0.3, r: 0.78 }}
          interactive
          spinBias={bias}
          onSunrise={setSunrises}
          onGrab={() => setGrabbed(true)}
        />
      </div>

      {/* A scrim weighted to the side the type sits on, falling to nothing well
          before the far edge so the limb stays visible where there is no text.
          Edge-anchored and full-bleed: a shape floating behind the words would
          read as an accident. */}
      <div
        {...layer({ scroll: 0.1 })}
        className="pointer-events-none absolute inset-0 -z-10 will-change-transform"
        style={{
          // Two different problems, two different scrims. On a wide screen the
          // globe is beside the type and a sideways wash is enough. On a narrow
          // one it is directly overhead, so the wash has to run down the frame
          // instead — measured, not guessed: the headline was landing at 1.85
          // against the lit limb, and body text at 2.28.
          background: wide
            ? "linear-gradient(100deg, color-mix(in oklab, var(--void-deep) 94%, transparent) 0%, color-mix(in oklab, var(--void-deep) 82%, transparent) 30%, color-mix(in oklab, var(--void-deep) 30%, transparent) 54%, transparent 70%)"
            : "linear-gradient(178deg, transparent 0%, color-mix(in oklab, var(--void-deep) 62%, transparent) 12%, color-mix(in oklab, var(--void-deep) 90%, transparent) 26%, color-mix(in oklab, var(--void-deep) 96%, transparent) 46%, color-mix(in oklab, var(--void-deep) 97%, transparent) 100%)",
        }}
      />

      <div className="mx-auto w-full max-w-[1560px]">
        <div className="max-w-2xl">
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
            <p className="mt-7 max-w-lg text-[17px] leading-relaxed text-[var(--ink-2)]">
              A tired crew member and an irreversible task are about to meet. HAVEN sees the
              collision coming, cites the rule that governs it, and hands a person the
              decision. When no rule fits, it says so.
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

          {/* The globe is not decoration, so it is allowed to say something.
              This counter is driven by the simulated station crossing the
              terminator — the same dot product the shader shades with. */}
          <Reveal delay={360}>
            <div className="mt-12 flex flex-wrap items-center gap-x-4 gap-y-2">
              <span
                className="readout text-[38px] leading-none"
                style={{ color: "var(--accent)" }}
              >
                {sunrises}
              </span>
              <p className="max-w-xs text-[13px] leading-relaxed text-[var(--ink-2)]">
                <span className="text-[var(--ink)]">sunrises</span> since you opened this page.
                In orbit a body clock gets about sixteen a day. That is the problem.
              </p>
            </div>

            <p
              className="mt-5 flex items-center gap-2 text-[12px] text-[var(--ink-3)] transition-opacity duration-700"
              style={{ opacity: grabbed ? 0 : 1 }}
            >
              <Hand size={13} />
              Drag the planet — it is simulated, not a picture.
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

/* The three reasons this cannot be eyeballed. One line each: the chart above
   them is doing the explaining now. */
const PROBLEMS: [string, string][] = [
  [
    "You cannot self-report it",
    "The gap above is invisible from the inside. It is the one instrument here you cannot trust.",
  ],
  [
    "Your best operators under-report the most",
    "They trained for years to be on this task. It is the question they will answer least honestly.",
  ],
  [
    "A tiredness number on its own is noise",
    "Tired during a rest period is fine. Tired forty minutes before an engine burn is not.",
  ],
];

function Problem() {
  return (
    <Section
      id="how"
      label="The problem"
      title="A tired brain does not feel broken"
      lead="It falls away hours before anybody notices. One crew member across one day, under the same model the engine runs."
    >
      <Reveal>
        <GlassCard className="p-5 sm:p-7">
          <AlertnessGap />
        </GlassCard>
      </Reveal>

      <div className="mt-7 grid gap-x-8 gap-y-6 md:grid-cols-3">
        {PROBLEMS.map(([title, body], i) => (
          <Reveal key={title} delay={i * 80} className="divide-top pt-4">
            <h3 className="text-[15px] font-medium leading-snug text-[var(--ink)]">{title}</h3>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-3)]">{body}</p>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

const RULES: [string, string][] = [
  [
    "Scores are calculated, never generated",
    "The model is handed every figure already computed. It may quote them. It cannot change them.",
  ],
  [
    "It flags risk, it never decides fitness",
    "No code path lets HAVEN defer, execute or reassign anything. The output is always for a person to action.",
  ],
  [
    "No citation, no recommendation",
    "A recommendation without a resolvable procedure citation is invalid and never shown. The flow refuses instead.",
  ],
];

function GoldenRule() {
  return (
    <Section
      label="The golden rule"
      title="The AI never produces a safety number"
      lead="Language models state wrong numbers with total confidence. So the line below is enforced in code, not asked for in a prompt."
    >
      <Reveal>
        <GlassCard className="p-5 sm:p-7">
          <HardLine />
        </GlassCard>
      </Reveal>

      <div className="mt-7 grid gap-x-8 gap-y-6 md:grid-cols-3">
        {RULES.map(([title, body], i) => (
          <Reveal key={title} delay={i * 80} className="divide-top pt-4">
            <span className="readout text-[12px] text-[var(--accent)]">
              Rule {String(i + 1).padStart(2, "0")}
            </span>
            <h3 className="mt-2 text-[15px] font-medium leading-snug text-[var(--ink)]">
              {title}
            </h3>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--ink-3)]">{body}</p>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

/**
 * The argument, running live on the front door.
 *
 * The product's strongest fact used to be reachable only by entering the
 * console, choosing the right one of eight questions, and scrolling past two
 * cards. A judge who never did all three never saw it. It is the same
 * `Counterfactual` the console renders, fed the real `eva_near_miss`
 * evaluation, so the page cannot drift from the engine: the score, the
 * condition lamps and the rule that applies instead are all read off the audit
 * record at load.
 *
 * Nothing here is written down. That is the point, and it is also why the
 * section removes itself when the engine cannot be reached rather than falling
 * back to numbers typed into the page — a landing page that hardcodes
 * "1.000" to make its case is doing the exact thing the case is against.
 */
function Overrule() {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [ready, setReady] = useState<"waiting" | "live" | "unavailable">("waiting");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const evaluation = await fetchEvaluation("eva_near_miss");
        const situation = evaluation.situations[0];
        if (!situation) throw new Error("no situation raised");
        const audit = await fetchAudit(situation.audit_ref);
        const computed = verdictFromAudit(situation, audit);
        if (cancelled) return;
        if (!computed) throw new Error("nothing to compare");
        setVerdict(computed);
        setReady("live");
      } catch {
        if (!cancelled) setReady("unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (ready === "unavailable") return null;

  return (
    <Section
      label="The overrule"
      title="A perfect score, on the wrong rule"
      lead="Retrieval ranks by wording. The checker judges each rule on its stated conditions — and it wins. Computed live, not written."
    >
      {/* No `GlassCard` around it, unlike the other sections: their visuals are
          bare SVG and need a surface, and this one already brings its own
          tinted panel and inset ring. Wrapping it would be a filled panel
          inside a filled panel — the thing the unboxing pass spent 42 boxes
          getting down to 3 to be rid of.

          The reserved height keeps arriving data from shoving the page under a
          reader who is already scrolling through it. */}
      <div className="min-h-[188px]">
        <Reveal>{ready === "live" ? <Counterfactual verdict={verdict} /> : null}</Reveal>
      </div>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

function Pipeline() {
  return (
    <Section
      label="The pipeline"
      title="Five steps. A person takes the last one."
      lead="Nothing in this sequence acts on the crew. It stops at a person."
    >
      <Reveal>
        <GlassCard className="p-5 sm:p-7">
          <PipelineRail />
        </GlassCard>
      </Reveal>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

const READS: [string, string][] = [
  ["Nothing to open", "The recommendation, who it concerns, and the figures behind it."],
  ["Nothing to open", "Four counts: what was measured, offered, allowed, and finally cited."],
  ["One click", "Every rule considered and how it was judged, condition by condition, plus the sealed log."],
];

function Layout() {
  return (
    <Section
      label="The console"
      title="Read it in three layers"
      lead="The first read gives you the answer. The audit gives you every condition behind it."
    >
      <div className="grid gap-7 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
        <Reveal>
          <GlassCard className="p-5 sm:p-7">
            <LayerStack />
          </GlassCard>
        </Reveal>

        <Reveal delay={90}>
          <div className="grid gap-6">
            {READS.map(([cost, body], i) => (
              <div key={i} className="divide-top pt-4">
                <span className="text-[11px] uppercase tracking-[0.15em] text-[var(--ink-3)]">
                  {cost}
                </span>
                <p className="mt-2 text-[14px] leading-relaxed text-[var(--ink-2)]">{body}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </div>

      <GlassCard className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-3 px-6 py-5">
        <Compass size={17} className="shrink-0 text-[var(--accent)]" />
        <p className="min-w-0 flex-1 text-[13px] leading-relaxed text-[var(--ink-2)]">
          A first visit runs a four-stop tour of those layers, replayable from the console at any
          time.
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

/** Every claim, with what backs it. `live` is the honest half of the argument. */
const LEDGER: [string, boolean, string][] = [
  ["Three-Process Model + NASA-TLX", true, "The published models, computed from the inputs shown."],
  ["Procedure search", true, "Rules that look right but are not are left in the results on purpose."],
  ["Precondition checker", true, "Judges each rule on its own stated conditions, separately from the model."],
  ["Refusal, roster and confidence gates", true, "All three run on every evaluation."],
  ["Hash-chained audit log", true, "Each entry is bound to the one before it."],
  ["Crew roster", false, "Representative people, not real individuals."],
  ["Sleep and task timelines", false, "Synthetic. No public live crew-timeline feed exists."],
  ["Rules marked prototype", false, "NASA flight-rule structure, written for this build. Labelled per row."],
  ["The reasoning model", false, "A scripted Granite stand-in unless a live provider is configured."],
];

function Honesty() {
  const live = LEDGER.filter(([, l]) => l).length;

  return (
    <Section
      label="Real vs simulated"
      title="What is real here, and what is not"
      lead="A system that claims to flag risk honestly would be a strange thing to describe dishonestly. So here is the register."
    >
      <Reveal>
        <GlassCard className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-4 sm:px-6">
            <span className="flex items-center gap-2 text-[13px] text-[var(--ink-2)]">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: "var(--ok)", boxShadow: "0 0 8px var(--ok)" }}
              />
              <span className="readout text-[16px] text-[var(--ink)]">{live}</span> running live
            </span>
            <span className="flex items-center gap-2 text-[13px] text-[var(--ink-2)]">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: "var(--warn)", boxShadow: "0 0 8px var(--warn)" }}
              />
              <span className="readout text-[16px] text-[var(--ink)]">
                {LEDGER.length - live}
              </span>{" "}
              simulated, and labelled
            </span>
          </div>

          <ul>
            {LEDGER.map(([subject, isLive, note]) => (
              <li
                key={subject}
                className="divide-top grid grid-cols-[auto_1fr] items-baseline gap-x-4 gap-y-1 px-5 py-3.5 sm:grid-cols-[128px_minmax(0,15rem)_1fr] sm:px-6"
              >
                <span
                  className="rounded-full px-2.5 py-[3px] text-center text-[11px] font-medium tracking-[0.06em]"
                  style={{
                    color: isLive ? "var(--ok)" : "var(--warn)",
                    background: `color-mix(in oklab, ${isLive ? "var(--ok)" : "var(--warn)"} 12%, transparent)`,
                    boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${isLive ? "var(--ok)" : "var(--warn)"} 30%, transparent)`,
                  }}
                >
                  {isLive ? "RUNNING" : "SIMULATED"}
                </span>
                <span className="text-[14px] font-medium text-[var(--ink)]">{subject}</span>
                <span className="col-span-2 text-[13px] leading-relaxed text-[var(--ink-3)] sm:col-span-1">
                  {note}
                </span>
              </li>
            ))}
          </ul>
        </GlassCard>
      </Reveal>
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
