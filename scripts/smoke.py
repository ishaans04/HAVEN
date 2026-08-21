"""Drive a running HAVEN and check it is doing what it claims.

    uv run --no-sync python -m scripts.smoke
    uv run --no-sync python -m scripts.smoke --base http://127.0.0.1:8000 --scenario eva_near_miss

Start the server first (``python -m scripts.run_haven``). This talks to it over
HTTP, exactly as the console does, so what it verifies is the assembled system
rather than the parts.

The checks are chosen for one property: **every one of them can fail while the
system looks fine.** A stale console still returns 200. A provider chain that
fell through to the offline stand-in still returns a well-formed recommendation.
A recommendation whose citation does not resolve still renders. None of these
raise, none of them log an error, and the console shows something plausible for
all of them.

That is the whole reason this exists. `pytest` proves the code is right against
a pinned mock; this proves the *deployment* is right against whatever is
actually configured — which on a machine with real credentials is a different
question with a different answer.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8000"
#: The discrimination scenario: three EVA-scoped passages, two of them
#: near-misses sharing the governing rule's vocabulary almost word for word.
DEFAULT_SCENARIO = "eva_near_miss"

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


class Report:
    """Collects results so every check runs, rather than stopping at the first."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def record(self, status: str, name: str, detail: str = "") -> None:
        self.rows.append((status, name, detail))
        print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))

    @property
    def failed(self) -> bool:
        return any(status == FAIL for status, _, _ in self.rows)


def get(base: str, path: str, timeout: float = 300.0):
    request = urllib.request.Request(f"{base}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def check_console(base: str, report: Report) -> None:
    try:
        status, body = get(base, "/", timeout=30)
    except urllib.error.HTTPError as exc:
        report.record(
            FAIL,
            "console served at /",
            f"HTTP {exc.code} -- the export is missing; run `cd web && npm run build`",
        )
        return
    ok = status == 200 and b"<html" in body.lower()
    report.record(PASS if ok else FAIL, "console served at /", f"HTTP {status}, {len(body):,} bytes")


def check_health(base: str, report: Report) -> dict:
    status, body = get(base, "/api/health", timeout=30)
    health = json.loads(body)
    tiers = health["tiers"]
    report.record(PASS if status == 200 else FAIL, "health", f"retrieval={tiers['retrieval']}")
    report.record(
        PASS,
        "reasoning configured",
        f"{tiers['reasoning_provider']} ({tiers['reasoning_model']})",
    )
    return health


def check_scenario(base: str, scenario: str, report: Report, health: dict) -> None:
    status, body = get(base, f"/api/scenarios/{scenario}/evaluate")
    if status != 200:
        report.record(FAIL, f"{scenario} evaluated", f"HTTP {status}")
        return
    payload = json.loads(body)
    tier = payload["tier_status"]

    # The question this script exists to answer. A chain that fell through is
    # working correctly and is not what a live demo is meant to show, and the
    # only difference visible from outside is this field.
    served, degraded = tier["served_by"], tier["degraded"]
    head = health["tiers"]["reasoning_provider"].split(" -> ")[0]
    if degraded:
        report.record(WARN, "served by the head of the chain", f"degraded, served by {served}")
        report.record(WARN, "  reason", str(tier.get("degraded_reason"))[:160])
    elif served.startswith(head):
        report.record(PASS, "served by the head of the chain", served)
    else:
        report.record(FAIL, "served by the head of the chain", f"expected {head}, got {served}")

    report.record(
        PASS if tier.get("corpus_manifest") else FAIL,
        "corpus manifest recorded",
        str(tier.get("corpus_manifest", ""))[:12] + "...",
    )

    situations = payload["situations"]
    report.record(PASS if situations else FAIL, f"{scenario} raised a Situation", f"{len(situations)} situation(s)")

    for situation in situations:
        _check_situation(base, situation, report)


def _check_situation(base: str, situation: dict, report: Report) -> None:
    outcome = situation["outcome"]
    recommendation, refusal = situation.get("recommendation"), situation.get("refusal")

    # S2, over the wire rather than in a unit test.
    exactly_one = (recommendation is None) != (refusal is None)
    report.record(PASS if exactly_one else FAIL, "exactly one of recommendation/refusal", outcome)

    if recommendation:
        citation = recommendation["citation"]
        report.record(PASS, "  action", f"{recommendation['action']} citing {citation['passage_id']}")

        # S5: a citation with no recorded verification is the failure this
        # system exists to prevent, and it renders identically to a good one.
        clauses = recommendation.get("verified_clauses") or []
        report.record(
            PASS if clauses and all(c["satisfied"] for c in clauses) else FAIL,
            "  checker verified every clause",
            f"{len(clauses)} clauses",
        )

        # S3: the citation must resolve to a real passage with matching document
        # and section. A fabricated identifier looks exactly as convincing.
        _, procedures = get(base, "/api/procedures", timeout=60)
        corpus = {p["passage_id"]: p for p in json.loads(procedures)}
        passage = corpus.get(citation["passage_id"])
        resolves = passage is not None and passage["doc"] == citation["doc"]
        report.record(PASS if resolves else FAIL, "  citation resolves in the corpus", citation["passage_id"])

        # S10: guidance and research may inform, never impose.
        if passage:
            authority = passage.get("authority", "")
            report.record(
                PASS if authority in ("authoritative", "prototype") else FAIL,
                "  cited passage may prescribe",
                f"authority={authority}",
            )
    else:
        report.record(PASS, "  refusal", f"{refusal['reason']} -> {refusal.get('escalate_to', '')}")

    # The ledger, verified end to end.
    _, audit = get(base, f"/api/audit/{situation['audit_ref']}", timeout=60)
    record = json.loads(audit)
    report.record(
        PASS if record.get("chain_valid") else FAIL,
        "  audit chain verifies",
        f"{len(record.get('steps', []))} steps, provider {record.get('provider')}",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smoke", description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    args = parser.parse_args(argv)

    print(f"HAVEN smoke test against {args.base}\n")
    report = Report()

    try:
        check_console(args.base, report)
        health = check_health(args.base, report)
        check_scenario(args.base, args.scenario, report, health)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"\n  cannot reach {args.base}: {exc}")
        print("  start it with:  uv run --no-sync python -m scripts.run_haven")
        return 2

    passed = sum(1 for status, _, _ in report.rows if status == PASS)
    print(f"\n  {passed}/{len(report.rows)} checks passed")
    if report.failed:
        print("  FAILED")
        return 1
    print("  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
