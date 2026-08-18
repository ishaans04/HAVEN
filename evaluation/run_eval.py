"""Measure the reasoning tier against the golden set.

    python -m evaluation.run_eval --provider mock
    python -m evaluation.run_eval --provider ollama
    python -m evaluation.run_eval --provider watsonx

Two accuracies are reported, and the distance between them is the point.

*Model accuracy* is what the provider proposed, judged against the label. It is
the number a system without a checker would have to live with.

*System accuracy* is what HAVEN actually did, after VERIFY disposed of that
proposal. A model that picks an inadmissible passage still yields a refusal, so
the system is right where the model was wrong -- and the gap between the two
columns is the checker earning its place, in a number rather than an argument.

A high model accuracy is pleasant. A high system accuracy is the requirement.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field

from evaluation.golden_set import CASES, GoldenCase
from haven.deterministic import preconditions
from haven.rag.corpus import BY_ID
from haven.reasoning.audit import AuditTrail
from haven.reasoning.llm import LLMUnavailable, ReasoningLLM, build_llm
from haven.reasoning.orchestrator import ReasoningFlow


@dataclass
class CaseResult:
    case: GoldenCase
    proposed: str | None
    verified: bool
    final_passage: str | None
    checker_disagreed: bool
    rejections: dict[str, str]
    latency_ms: float
    error: str = ""

    @property
    def model_correct(self) -> bool:
        return self.proposed == self.case.governs

    @property
    def system_correct(self) -> bool:
        """What HAVEN did, after the checker disposed of the proposal."""
        return self.final_passage == self.case.governs

    @property
    def unsafe(self) -> bool:
        """Cited a passage that does not govern. The failure that matters."""
        return self.final_passage is not None and self.final_passage != self.case.governs


@dataclass
class Report:
    provider: str
    model_id: str
    results: list[CaseResult] = field(default_factory=list)

    def _rate(self, subset: list[CaseResult], predicate) -> float:
        return (sum(1 for r in subset if predicate(r)) / len(subset)) if subset else 1.0

    @property
    def governing(self) -> list[CaseResult]:
        return [r for r in self.results if not r.case.should_refuse]

    @property
    def refusing(self) -> list[CaseResult]:
        return [r for r in self.results if r.case.should_refuse]

    def summary(self) -> dict:
        refused = [r for r in self.results if r.final_passage is None]
        correctly_refused = [r for r in refused if r.case.should_refuse]
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "cases": len(self.results),
            "model_accuracy": self._rate(self.results, lambda r: r.model_correct),
            "system_accuracy": self._rate(self.results, lambda r: r.system_correct),
            "selection_accuracy_when_a_rule_governs": self._rate(self.governing, lambda r: r.system_correct),
            "refusal_recall": self._rate(self.refusing, lambda r: r.final_passage is None),
            "refusal_precision": (len(correctly_refused) / len(refused)) if refused else 1.0,
            # The one that must be zero: a citation that does not govern.
            "unsafe_citations": sum(1 for r in self.results if r.unsafe),
            # How often the checker had to overrule the model. Zero means the
            # model needed no help; it does not mean the checker is unnecessary.
            "checker_saves": sum(1 for r in self.results if not r.model_correct and r.system_correct),
            "checker_disagreements": sum(1 for r in self.results if r.checker_disagreed),
            "near_miss_rejection_rate": self._near_miss_rejection_rate(),
            "median_latency_ms": self._median_latency(),
            "errors": sum(1 for r in self.results if r.error),
        }

    def _near_miss_rejection_rate(self) -> float:
        """Of every labelled near-miss offered, how many were not selected."""
        offered = rejected = 0
        for result in self.results:
            for passage_id in result.case.why_not:
                offered += 1
                if result.proposed != passage_id:
                    rejected += 1
        return (rejected / offered) if offered else 1.0

    def _median_latency(self) -> float:
        values = sorted(r.latency_ms for r in self.results)
        return values[len(values) // 2] if values else 0.0


def evaluate_case(case: GoldenCase, llm: ReasoningLLM) -> CaseResult:
    """Run one case through SELECT and VERIFY, exactly as the graph would."""
    trail = AuditTrail(audit_ref=f"EVAL-{case.case_id}", situation_id=case.case_id)
    flow = ReasoningFlow(retriever=None, llm=llm, trail=trail)
    payloads = case.prose()

    started = time.perf_counter()
    try:
        selection = flow.select(case.facts, payloads) if payloads else {"governing_passage_id": None, "rejected": []}
        error = ""
    except LLMUnavailable as exc:
        selection, error = {"governing_passage_id": None, "rejected": []}, str(exc)
    latency = (time.perf_counter() - started) * 1000.0

    # The checker's independent view, over the full candidate set.
    admissibility = {
        pid: preconditions.check(
            BY_ID[pid].applies_when,
            BY_ID[pid].prescribes,
            case.facts,
            authority=BY_ID[pid].authority,
        )
        for pid in case.candidate_ids
    }
    verdict = flow.verify(admissibility, selection)

    return CaseResult(
        case=case,
        proposed=selection.get("governing_passage_id"),
        verified=verdict.verified,
        final_passage=verdict.passage_id if verdict.verified else None,
        checker_disagreed=verdict.checker_disagreed,
        rejections={r["passage_id"]: r.get("why", "") for r in selection.get("rejected", [])},
        latency_ms=latency,
        error=error,
    )


def run(provider: str) -> Report:
    llm = build_llm(provider) if provider else build_llm()
    report = Report(provider=llm.provider, model_id=llm.model_id)
    for case in CASES:
        report.results.append(evaluate_case(case, llm))
    return report


def _print(report: Report, verbose: bool) -> None:
    summary = report.summary()
    print("=" * 78)
    print(f"{summary['provider']}  /  {summary['model_id']}")
    print("=" * 78)

    if verbose:
        for result in report.results:
            mark = "ok  " if result.system_correct else "FAIL"
            note = ""
            if not result.model_correct and result.system_correct:
                note = f"  (checker overruled {result.proposed or 'a refusal'})"
            elif result.unsafe:
                note = "  <-- UNSAFE CITATION"
            print(
                f"  {mark} {result.case.case_id:<28} "
                f"want={str(result.case.governs):<12} got={str(result.final_passage):<12}{note}"
            )
        print()

    def pct(key: str) -> str:
        return f"{summary[key] * 100:5.1f}%"

    print(f"  cases                     {summary['cases']}")
    print(f"  model accuracy            {pct('model_accuracy')}   (what the provider proposed)")
    print(f"  system accuracy           {pct('system_accuracy')}   (what HAVEN did, after VERIFY)")
    print(f"  selection, rule governs   {pct('selection_accuracy_when_a_rule_governs')}")
    print(f"  refusal recall            {pct('refusal_recall')}")
    print(f"  refusal precision         {pct('refusal_precision')}")
    print(f"  near-miss rejection       {pct('near_miss_rejection_rate')}")
    print(f"  checker saves             {summary['checker_saves']}   (model wrong, system right)")
    print(f"  checker disagreements     {summary['checker_disagreements']}")
    print(f"  median latency            {summary['median_latency_ms']:.1f} ms")
    print(f"  provider errors           {summary['errors']}")
    print()
    verdict = "PASS" if summary["unsafe_citations"] == 0 else "FAIL"
    print(f"  unsafe citations          {summary['unsafe_citations']}   <-- must be 0    [{verdict}]")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="", help="mock | ollama | watsonx (default: configured)")
    parser.add_argument("--json", action="store_true", help="emit the summary as JSON")
    parser.add_argument("--verbose", action="store_true", help="one line per case")
    args = parser.parse_args()

    report = run(args.provider)
    summary = report.summary()

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print(report, args.verbose)

    # Non-zero exit on an unsafe citation, so CI can gate on it.
    return 1 if summary["unsafe_citations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
