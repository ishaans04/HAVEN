"""Stage 4b: ADMISSIBILITY -- what the checker believes, before the model speaks.

Runs ``haven.deterministic.preconditions.check`` over **every** retrieved
candidate and logs a clause-by-clause verdict for each.

It deliberately does **not** filter the candidate set. Two reasons, and both
matter:

  * A near-miss is inadmissible by construction -- that is what makes it a
    near-miss. Filtering here would delete the discrimination case the system
    exists to demonstrate: ``eva_near_miss`` would never see the planning-phase
    sleep-shifting passage, and the model's rejection of it would be a
    tautology rather than a reading.
  * Pre-cleaning the candidate set is the same mistake as showing the model
    ``applies_when``, arrived at from the other direction. Either way the model
    stops reading and starts trusting.

What it produces is a record: an independent verdict, timestamped and hashed
into the trail *before* the reasoning tier is invoked, so that VERIFY's later
agreement or disagreement is a comparison of two positions taken separately
rather than one position and an echo.
"""

from __future__ import annotations

from typing import Any

from haven.graph.state import SituationState


def admissibility_node(state: SituationState) -> dict[str, Any]:
    return {"admissibility": state["flow"].admissibility(state["facts"], state["candidates"])}
