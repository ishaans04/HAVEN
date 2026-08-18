"""A minimal, valid PDF, built in-process.

The compiler's tests need real PDFs. Committing binary fixtures would mean
nobody can see what is being tested without opening them in a viewer, and
downloading NASA documents at test time would make the suite depend on the
network — which `tests/test_offline_guard.py` exists to forbid.

So the fixture is generated from text. This writes genuine PDF syntax rather
than mocking a reader, which matters: `pdfplumber` and `pypdf` are exercised for
real, and a change that broke extraction would fail here rather than only
against documents nobody runs in CI.

Deliberately minimal — Helvetica, one content stream per page, no compression.
Enough to be parsed by both readers, and small enough to read as source.
"""

from __future__ import annotations


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _content_stream(lines: list[str], *, leading: int = 14) -> bytes:
    body = ["BT", "/F1 10 Tf", f"{leading} TL", "56 760 Td"]
    for line in lines:
        # Wrap crudely at a width Helvetica 10pt fits on US Letter, so the
        # extracted text has realistic line breaks rather than one long line.
        for segment in _wrap(line, 92) or [""]:
            body.append(f"({_escape(segment)}) Tj")
            body.append("T*")
    body.append("ET")
    return "\n".join(body).encode("latin-1", "replace")


def _wrap(line: str, width: int) -> list[str]:
    if not line:
        return [""]
    words, out, current = line.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    return out


def build_pdf(pages: list[list[str]]) -> bytes:
    """A PDF whose pages contain the given lines of text."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: list[int] = []
    content_ids: list[int] = []
    for lines in pages:
        stream = _content_stream(lines)
        content_ids.append(add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)))
        page_ids.append(0)  # placeholder, filled once the pages node exists

    pages_id = add(b"")  # placeholder

    for index, content_id in enumerate(content_ids):
        page_ids[index] = add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (pages_id, font_id, content_id)
        )

    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    objects[pages_id - 1] = b"<< /Type /Pages /Count %d /Kids [%s] >>" % (len(page_ids), kids)

    catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog_id,
        xref_at,
    )
    return bytes(out)


# A page in the shape of NASA-STD-3001: bracketed requirement identifiers, a
# rule, and — crucially — an exception that belongs to the rule above it. That
# exception is what a fixed-size splitter severs.
STANDARD_PAGE = [
    "NASA-STD-3001 VOLUME 2, REVISION D",
    "",
    "6.2 CREW SLEEP AND CIRCADIAN ALIGNMENT",
    "",
    "[V2 7003] Sleep Opportunity",
    "The system shall provide each crewmember a sleep opportunity of at least 8 hours "
    "per 24-hour period. This requirement does not apply during launch, entry, or "
    "declared contingency operations, during which the flight director may authorise "
    "a reduced sleep opportunity.",
    "",
    "[V2 7004] Circadian Alignment",
    "The system shall align the crew work-rest schedule to a 24-hour circadian period. "
    "Where mission operations require a shifted schedule, the shift shall not exceed "
    "one hour per 24-hour period without a protected adaptation period.",
    "",
    "[V2 7005] Sleep Environment",
    "The system shall provide a sleep environment that limits acoustic, luminous, and "
    "thermal disturbance during the crew sleep period.",
]

SECOND_PAGE = [
    "NASA-STD-3001 VOLUME 2, REVISION D",
    "",
    "6.3 WORKLOAD AND TASK SCHEDULING",
    "",
    "[V2 7101] Sustained Workload",
    "The system shall limit sustained crew workload such that task demand does not "
    "exceed the crew capability established for the mission phase. Workload shall be "
    "assessed against the planned timeline prior to execution.",
]
