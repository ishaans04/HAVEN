import type { Situation } from "./types";

/**
 * The consultation layer.
 *
 * HAVEN is something you ask, not something you watch. Everything here turns
 * the engine's own codes into the question a person would actually have said
 * out loud, and the answer they would actually have wanted back.
 *
 * The rule this file obeys: **no invented semantics.** Every headline is keyed
 * off a code the backend emitted, and the engine's own precise label always
 * travels with it. If the backend adds an action tomorrow, the fallback is that
 * label rather than a guess, so a new case degrades to "correct but plain"
 * rather than to "confidently wrong".
 */

/**
 * What the person is about to do, in the words a non-specialist would use.
 * Keyed on `task_type`, which is a closed set in the schema.
 */
const DOING: Record<string, string> = {
  orbital_burn: "fly this burn",
  eva: "go outside",
  medical_contingency: "handle this medical emergency",
  docking: "fly this docking",
  robotics_capture: "fly this capture",
  hatch_operation: "run this drill",
  science_ops: "run this science pass",
};

/** "R. Alvarez" → "Alvarez". A question uses the name you would say aloud. */
export const surname = (name: string) => name.trim().split(/\s+/).pop() ?? name;

/** The question this situation is really asking. */
export function questionFor(situation: Situation | null): string {
  if (!situation) return "Is anyone at risk today?";
  const doing = DOING[situation.task_type] ?? "take this on";
  return `Is ${surname(situation.crew_member_name)} fit to ${doing}?`;
}

/**
 * The answer, in two registers.
 *
 * `headline` is what a person hears. `precise` is what the engine said, and it
 * is always shown next to the headline — the plain words are a way in, not a
 * replacement for the operator's term.
 */
const HEADLINE: Record<string, string> = {
  second_operator_verify: "Not alone.",
  short_rest_then_proceed: "Rest first.",
  task_deferral: "Not now.",
};

export type AnswerKind = "recommendation" | "refusal" | "quiet";

export type Answer = {
  headline: string;
  precise: string;
  kind: AnswerKind;
  tone: "ok" | "warn" | "bad";
};

export function answerFor(situation: Situation | null): Answer {
  if (!situation) {
    return {
      headline: "Nobody.",
      precise: "No situation raised",
      kind: "quiet",
      tone: "ok",
    };
  }

  if (situation.outcome === "refusal") {
    return {
      // The most important sentence in the product. HAVEN declining to answer
      // is the whole claim: the model does not get the last word.
      headline: "HAVEN won't answer this.",
      precise: situation.refusal?.reason_label ?? "Refused",
      kind: "refusal",
      tone: "bad",
    };
  }

  const action = situation.recommendation?.action ?? "";
  const label = situation.recommendation?.action_label ?? "Recommendation";
  return {
    headline: HEADLINE[action] ?? label,
    precise: label,
    kind: "recommendation",
    tone: "warn",
  };
}

/**
 * The eight cases, as questions somebody would think to ask.
 *
 * Deliberately about the *situation* rather than the crew member: these are read
 * before any data has loaded, so naming a person here would hardcode roster
 * detail that belongs to the engine. Once a case is open, the console asks the
 * specific question, built from the evaluation itself by `questionFor`.
 *
 * Any scenario the backend adds and this map does not know falls back to the
 * API's own title, so the picker can never go stale or lie.
 */
export const ASK: Record<string, { question: string; why: string }> = {
  burn_fatigue: {
    question: "Can a tired commander fly a reboost burn?",
    why: "The core case. Chronic sleep restriction before a high-criticality burn.",
  },
  eva_near_miss: {
    question: "Is this astronaut cleared to go outside?",
    why: "A rule that looks exactly right is in the running. Watch it get thrown out.",
  },
  no_procedure: {
    question: "What happens when no rule covers it?",
    why: "A medical emergency the rulebook never anticipated.",
  },
  roster_block: {
    question: "What if the safe answer breaks the crew roster?",
    why: "The fix is sound, and there is nobody qualified left to do the job.",
  },
  circadian_trap: {
    question: "Slept fine, but it is 03:20. Still safe?",
    why: "Enough sleep, wrong hour. The body clock disagrees with the sleep log.",
  },
  thin_data: {
    question: "What if the sleep data is too thin to judge?",
    why: "A sparse record. HAVEN would rather say nothing than guess.",
  },
  nominal_ops: {
    question: "What does it look like when all is well?",
    why: "A quiet console is a working one. Nothing is flagged, and it says so.",
  },
  provider_outage: {
    question: "What if the AI goes offline mid-shift?",
    why: "The reasoning tier is unreachable. The maths still runs.",
  },
};
