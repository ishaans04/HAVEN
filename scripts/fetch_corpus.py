"""Acquire the source documents named in the corpus registry.

    uv run python -m scripts.fetch_corpus            # fetch what is missing, verify the rest
    uv run python -m scripts.fetch_corpus --pin      # record checksums for newly acquired files
    uv run python -m scripts.fetch_corpus --verify   # verify only; download nothing

The PDFs are not in the repository. They are public — every document in the
registry is cleared for public release by NASA — but redistribution belongs to
the publisher, and a repository that carries a stale private copy of a living
standard is worse than one that carries none.

What *is* in the repository is enough to reproduce the acquisition exactly: the
canonical URL, the document number and revision, the approval date, and a pinned
SHA-256. That last one does the work. A standards body replacing a PDF in place
is not hypothetical, and it is the failure mode this script exists for: without a
pin, a corpus recompiled six months later would quietly be a corpus of a
different revision, and every decision made under it would cite section numbers
that had moved.

So a checksum mismatch is refused, not warned about. The remedy is deliberate —
verify the new revision, update the registry, re-review the passages it changes —
and that is exactly the amount of friction the situation deserves.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

from compiler.registry import RegistryError, SourceRecord, read, summarise, write

DEFAULT_REGISTRY = Path("corpus/sources.json")

#: Some publishers reject the default urllib agent outright.
USER_AGENT = "HAVEN-corpus-fetch/1.0 (+https://github.com/ishaans04/HAVEN)"

#: Every registry entry is a PDF, and a redirect to an HTML error page is the
#: usual way a dead link presents itself. Checking the magic bytes turns that
#: into a refusal rather than into an unreadable document three steps later.
PDF_MAGIC = b"%PDF"


def digest(path: Path) -> tuple[str, int]:
    """SHA-256 and size, streamed — some of these documents are 25 MB."""
    sha, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            sha.update(block)
            size += len(block)
    return sha.hexdigest(), size


def download(url: str, destination: Path) -> None:
    """Fetch to a temporary file, then move into place.

    Downloading straight to the destination would leave a truncated PDF behind
    on a dropped connection, and a truncated PDF extracts as a document that is
    simply missing its later requirements — a silent gap in the corpus, which is
    the failure this whole pipeline is built to make impossible.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, suffix=".part") as temporary:
        staging = Path(temporary.name)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, open(staging, "wb") as handle:
            shutil.copyfileobj(response, handle)
        with open(staging, "rb") as handle:
            if handle.read(len(PDF_MAGIC)) != PDF_MAGIC:
                raise RuntimeError(f"{url} did not return a PDF (probably a redirect to an error page)")
        staging.replace(destination)
    finally:
        staging.unlink(missing_ok=True)


def acquire(record: SourceRecord, *, pin: bool, verify_only: bool) -> tuple[SourceRecord, str]:
    """Ensure one document is present and is the one the registry names."""
    if not record.path.exists():
        if verify_only:
            return record, "missing"
        try:
            download(record.pdf_url, record.path)
        except (urllib.error.URLError, RuntimeError, OSError) as exc:
            return record, f"FAILED — {exc}"

    checksum, size = digest(record.path)

    if not record.sha256:
        if not pin:
            return record, (f"unpinned ({checksum[:16]}…, {size:,} bytes) — re-run with --pin to record it")
        return replace(record, sha256=checksum, bytes=size), f"pinned {checksum[:16]}… ({size:,} bytes)"

    if checksum != record.sha256:
        return record, (
            f"REFUSED — checksum mismatch.\n"
            f"      registry: {record.sha256}\n"
            f"      on disk:  {checksum}\n"
            f"      This file is not the revision the registry names. If the publisher has "
            f"issued a new one, verify it, update the registry's revision, published date "
            f"and verification note, and re-review every passage compiled from it. Do not "
            f"simply re-pin."
        )

    return record, f"verified {checksum[:16]}… ({size:,} bytes)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fetch_corpus", description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--pin", action="store_true", help="record checksums for newly acquired files")
    parser.add_argument("--verify", action="store_true", help="verify what is present; download nothing")
    args = parser.parse_args(argv)

    registry = Path(args.registry)
    try:
        records = read(registry)
    except RegistryError as exc:
        print(f"registry: {exc}", file=sys.stderr)
        return 2

    print(f"{registry} lists {len(records)} document(s)\n")

    updated: list[SourceRecord] = []
    problems = 0
    for record in records:
        label = f"{record.doc_id} ({record.authority})"
        print(f"  {label}")
        print(f"      {record.citation()}")
        result, status = acquire(record, pin=args.pin, verify_only=args.verify)
        updated.append(result)
        if status.startswith(("REFUSED", "FAILED")) or status == "missing":
            problems += 1
        print(f"      {status}\n")

    if args.pin and any(new.sha256 != old.sha256 for new, old in zip(updated, records, strict=True)):
        write(registry, updated)
        print(f"Updated {registry} with the newly pinned checksums. Review the diff before committing.\n")

    counts = summarise(updated)
    print(
        f"{counts['present']}/{counts['documents']} present, {counts['pinned']} pinned "
        f"({counts['authoritative']} authoritative, {counts['guidance']} guidance, "
        f"{counts['research']} research)"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
