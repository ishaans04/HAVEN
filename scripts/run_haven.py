"""Start HAVEN: check the console is built, check the environment, then serve.

    uv run --no-sync python -m scripts.run_haven
    uv run --no-sync python -m scripts.run_haven --port 8080 --reload
    uv run --no-sync python -m scripts.run_haven --skip-checks

One process serves the console at ``/`` and the API under ``/api`` from the same
origin, so there is one port and nothing to configure.

The checks in front of the server exist because both failures they catch are
silent. A missing console export does not stop the API starting -- development
deliberately runs the console on its own port -- so the first sign is a 404 at
the root of a server that reported itself healthy. And a provider chain that
falls through to the offline stand-in is *correct* behaviour, which means an
expired key looks exactly like a working demo until somebody reads Zone 6.

Neither check refuses to start. They print what is true and let the operator
decide, because a launcher that would not run without watsonx credentials would
contradict the offline guarantee it is launching.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from haven.config import LLM
from haven.rag.corpus import CORPUS, CORPUS_MANIFEST
from haven.reasoning.chain import configured_chain

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSOLE_DIR = REPO_ROOT / "web" / "out"


def check_console() -> bool:
    """Is the static export present, and does it look freshly built?"""
    index = CONSOLE_DIR / "index.html"
    if not index.exists():
        print("  console      NOT BUILT -- the API will serve /api but 404 at /")
        print("               fix:  cd web && npm ci && npm run build")
        return False

    # A stale export is worse than a missing one: the page loads, looks right,
    # and shows a version of the UI that no longer matches the API it is
    # talking to. Comparing against the sources is cheap and catches the case
    # where somebody edited a component and forgot to rebuild.
    sources = list((REPO_ROOT / "web" / "src").rglob("*.tsx")) + list((REPO_ROOT / "web" / "src").rglob("*.ts"))
    newer = [p for p in sources if p.stat().st_mtime > index.stat().st_mtime]
    if newer:
        print(f"  console      STALE -- {len(newer)} source file(s) changed since the last build")
        print(f"               newest: {newer[0].relative_to(REPO_ROOT).as_posix()}")
        print("               fix:  cd web && npm run build")
        return False

    print(f"  console      built, serving from {CONSOLE_DIR.relative_to(REPO_ROOT).as_posix()}")
    return True


def check_reasoning() -> bool:
    """Say which provider will be tried, without spending a token to find out."""
    chain = configured_chain()
    print(f"  reasoning    {' -> '.join(chain)}  ({LLM.model_id})")

    if chain == ("mock",):
        print("               the offline stand-in only. Set HAVEN_LLM_CHAIN=watsonx,mock in .env")
        print("               to use watsonx; see scripts/check_providers for a live check.")
        return False

    if "watsonx" in chain and not (LLM.watsonx_api_key and LLM.watsonx_project_id):
        print("               !! watsonx is in the chain but its credentials are not set,")
        print("               !! so every request will fall through to the stand-in.")
        return False
    return True


def check_corpus() -> None:
    print(f"  corpus       {len(CORPUS)} passages, manifest {CORPUS_MANIFEST[:12]}...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_haven", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="restart on source changes")
    parser.add_argument("--skip-checks", action="store_true")
    args = parser.parse_args(argv)

    if not args.skip_checks:
        print("HAVEN")
        console_ok = check_console()
        check_reasoning()
        check_corpus()
        print()
        if not console_ok:
            # Worth a beat: the server is about to start and answer /api
            # perfectly while 404-ing the page the operator opens.
            print("  Starting anyway -- the API works without the console.\n")

    print(f"  http://{args.host}:{args.port}        console")
    print(f"  http://{args.host}:{args.port}/docs   API reference")
    print("  Ctrl-C to stop\n")

    # uvicorn logs through the logging module to stderr and never touches this
    # buffer, so without an explicit flush every line above sits unwritten until
    # the process exits -- and if it is killed rather than stopped, is lost
    # entirely. A preflight nobody can read is not a preflight.
    sys.stdout.flush()

    import uvicorn

    uvicorn.run(
        "haven.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
