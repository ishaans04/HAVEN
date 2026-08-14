"""Export the OpenAPI schema to a file, for TypeScript generation.

    python -m scripts.export_openapi

The schema is written to ``openapi.json`` at the repository root and committed.
That serves two purposes beyond feeding ``openapi-typescript``:

  * The contract becomes visible in review. A change to ``contracts.py`` shows up
    as a schema diff in the same commit, which is what makes the locked contract
    (PRD section 5) actually reviewable rather than merely declared.
  * CI can regenerate the TypeScript without starting a server. Fetching
    ``/openapi.json`` from a live uvicorn would work locally and be a liability
    in a pipeline.

Determinism matters: the file is regenerated in CI and compared with
``git diff --exit-code``, so any nondeterminism here reads as drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from haven.api.main import app  # noqa: E402

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def export() -> Path:
    schema = app.openapi()
    # sort_keys so the output depends on the models, not on dict insertion order,
    # and a trailing newline so the file is well-formed for git.
    #
    # newline="\n" is load-bearing, not tidiness. Without it Python's text mode
    # writes CRLF on Windows while .gitattributes normalises the committed file
    # to LF, so the CI drift check would pass on Ubuntu and fail on every
    # developer's machine the moment they regenerated -- reporting drift that
    # does not exist and hiding drift that does.
    OUTPUT.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return OUTPUT


def main() -> None:
    path = export()
    schema = json.loads(path.read_text(encoding="utf-8"))
    print(f"wrote {path}")
    print(f"  {len(schema['components']['schemas'])} schemas, {len(schema['paths'])} paths")


if __name__ == "__main__":
    main()
