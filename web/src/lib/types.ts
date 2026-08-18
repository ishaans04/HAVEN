/**
 * The frontend half of the locked contract (backend/app/contracts.py).
 *
 * These were hand-mirrored in v1, on the reasoning that a drift between the two
 * halves would show up as a type error. That only held while someone remembered
 * to edit both files. Now the shapes are *generated* from the backend's OpenAPI
 * schema into `api-types.ts`, and this module is the friendly-name layer over
 * them — so a contract change that is not mirrored here is a compile error
 * rather than a silently reshaped payload.
 *
 * Regenerate with `npm run gen:types` (CI fails on drift).
 *
 * Everything below is derived from the schema except the two candidate shapes at
 * the bottom, which are documented there.
 */

import type { components } from "./api-types";

type Schemas = components["schemas"];

// --------------------------------------------------------------------------
// Enumerations — derived from the field that declares them, not restated, so a
// new ActionType in Python cannot go missing here.
// --------------------------------------------------------------------------
export type Criticality = Schemas["Task"]["criticality"];
export type RiskLevel = Schemas["Situation"]["risk_level"];
export type Confidence = Schemas["Situation"]["confidence"];
export type Outcome = Schemas["Situation"]["outcome"];
export type ActionType = Schemas["Recommendation"]["action"];
export type RefusalReason = Schemas["Refusal"]["reason"];
export type CrewStatus = Schemas["CrewReadiness"]["status"];
export type CrewTrend = Schemas["CrewReadiness"]["trend"];

// --------------------------------------------------------------------------
// Request
// --------------------------------------------------------------------------
export type EvaluationWindow = Schemas["EvaluationWindow"];
export type SleepEntry = Schemas["SleepEntry"];
export type DutyEntry = Schemas["DutyEntry"];
export type CrewMember = Schemas["CrewMember"];
export type Task = Schemas["Task"];
export type EvaluationRequest = Schemas["EvaluationRequest"];

// --------------------------------------------------------------------------
// Response
// --------------------------------------------------------------------------
export type Citation = Schemas["Citation"];
export type ClauseDetail = Schemas["ClauseDetail"];
export type ScheduleImpact = Schemas["ScheduleImpact"];
export type Projection = Schemas["Projection"];
export type Recommendation = Schemas["Recommendation"];
export type BestCandidate = Schemas["BestCandidate"];
export type Refusal = Schemas["Refusal"];
export type Evidence = Schemas["Evidence"];
export type Situation = Schemas["Situation"];
export type CurvePoint = Schemas["CurvePoint"];
export type CrewReadiness = Schemas["CrewReadiness"];
export type TimelineTask = Schemas["TimelineTask"];
export type TierStatus = Schemas["TierStatus"];
export type EvaluationResponse = Schemas["EvaluationResponse"];

// --------------------------------------------------------------------------
// Audit, decisions, corpus, scenarios
// --------------------------------------------------------------------------
export type AuditStep = Schemas["AuditStep"];
export type AuditRecord = Schemas["AuditRecord"];
export type DecisionRequest = Schemas["DecisionRequest"];
export type DecisionRecord = Schemas["DecisionRecord"];
export type ProcedureSummary = Schemas["ProcedureSummary"];
export type ScenarioSummary = Schemas["ScenarioSummary"];

// --------------------------------------------------------------------------
// Shapes read out of the audit payload
//
// `AuditStep.inputs` and `outputs` are `Record<string, unknown>` on both sides:
// each step logs a different shape, and the contract deliberately does not
// enumerate them. These two describe what the RETRIEVE and SELECT steps put
// there, and are the one place the console asserts a shape the schema does not
// guarantee. Zone 3 narrows through them.
//
// They are hand-written on purpose. Typing them properly means a discriminated
// union keyed on `step`, which belongs with the ledger rework rather than here.
// --------------------------------------------------------------------------
export interface RetrievedCandidate {
  passage_id: string;
  doc: string;
  section: string;
  title: string;
  relevance: number;
  lexical: number;
  tag_match: number;
}

// The reasoning tier now reports *why* it rejected a passage and nothing else.
// It used to report a `relevance` float beside it, derived by arithmetic on the
// retrieval similarity score; that number looked like a judgement and was not
// one, and nothing decides anything by it any more.
export interface RejectedCandidate {
  passage_id: string;
  why: string;
}
