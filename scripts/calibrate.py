"""Run every scenario and print what branch it reached.

Used during build to confirm each scenario lands where the PRD says it should,
and kept because it is the fastest way to see the whole system's behaviour at
once after a threshold change.

    python -m scripts.calibrate
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from haven import engine  # noqa: E402
from haven.api.main import UnavailableLLM  # noqa: E402
from haven.contracts import EvaluationRequest  # noqa: E402
from haven.data.scenarios import SCENARIOS  # noqa: E402
from haven.reasoning.audit import AUDIT  # noqa: E402
from haven.reasoning.llm import build_llm  # noqa: E402


def main() -> None:
    for scenario in SCENARIOS:
        request = EvaluationRequest.model_validate(scenario.build())
        llm = UnavailableLLM() if scenario.id == "provider_outage" else build_llm()
        response = engine.evaluate(request, llm=llm)

        print("=" * 96)
        print(f"{scenario.id:<18} {scenario.title}")
        print(f"  archived low-risk: {response.archived_low_risk}")
        for r in response.readiness:
            print(
                f"  {r.crew_member} {r.name:<12} alert={r.alertness_score:.3f} "
                f"base={r.baseline_alertness:.3f} d={r.delta_vs_baseline:+.3f} "
                f"tlx={r.workload_score:5.1f} debt={r.sleep_debt_h:4.1f}h {r.status:<8} {r.trend}"
            )
        if not response.situations:
            print("  -- no situations raised --")
        for s in response.situations:
            print(
                f"  [{s.situation_id}] {s.crew_member} / {s.task} ({s.task_type}, {s.task_criticality}) "
                f"alert={s.alertness_score} tlx={s.workload_score} circ={s.circadian_flag} "
                f"risk={s.risk_level} conf={s.confidence} -> {s.outcome.upper()}"
            )
            if s.recommendation:
                rec = s.recommendation
                print(f"      action   : {rec.action}  [{rec.citation.doc} {rec.citation.section}]")
                print(f"      roster_ok: {rec.schedule_impact.roster_ok}  alt={rec.schedule_impact.alternate}")
                print(f"      text     : {rec.rationale[:200]}")
            if s.refusal:
                print(f"      reason   : {s.refusal.reason}")
                print(f"      searched : {s.refusal.searched}")
                print(f"      best     : {s.refusal.best_candidate}")
                print(f"      proposed : {s.refusal.model_selected}  disagreed={s.refusal.checker_disagreed}")
                for clause in s.refusal.failed_clauses:
                    print(f"      UNMET    : {clause.clause:<24} {clause.explanation[:70]}")

            trail = AUDIT.get(s.audit_ref)
            if trail:
                for entry in trail.entries:
                    if entry.step == "RETRIEVE":
                        for c in entry.outputs["candidates"]:
                            print(f"      retrieved: {c['passage_id']:<10} rel={c['relevance']:.3f} {c['title'][:56]}")
                    if entry.step == "ADMISSIBILITY":
                        admissible = entry.outputs["admissible"]
                        print(f"      checker  : admissible={admissible or 'none'}")
                    if entry.step == "SELECT":
                        for r in entry.outputs.get("rejected", []):
                            print(f"      REJECTED : {r['passage_id']:<10} -- {r['why'][:80]}")
                    if entry.step == "VERIFY":
                        print(
                            f"      VERIFY   : verified={entry.outputs['verified']} "
                            f"disagreed={entry.outputs['checker_disagreed']} "
                            f"reason={entry.outputs['refusal_reason']}"
                        )
                print(f"      steps    : {' -> '.join(e.step for e in trail.entries)}")
                print(f"      chain    : {'valid' if trail.verify() else 'BROKEN'} ({len(trail.entries)} steps)")
        ts = response.tier_status
        if ts.degraded:
            print(f"  DEGRADED: {ts.degraded_reason}")


if __name__ == "__main__":
    main()
