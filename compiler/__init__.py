"""The corpus compiler. Offline, and never on the request path.

HAVEN's deepest admitted gap: `applies_when` is authored metadata. Somebody read
a passage and hand-wrote the machine-checkable preconditions beside it. That is
fine for eleven passages written to exercise a reasoning tier, and it does not
survive contact with a real procedure library.

This package turns source documents into passages carrying those preconditions,
under human review. Its output is a versioned artefact with a manifest digest,
which the runtime loads; the compiler itself never runs at request time, and a
test asserts nothing under `haven/` imports it.

That separation is the point. Extraction uses a model, and a model authoring
safety preconditions live would be the whole architecture defeated. Doing it
ahead of time, with a human approving each one, means the runtime only ever
reads preconditions a person signed off — which is what lets the deterministic
checker be trusted as the thing that disposes.

Requires the compiler extra: ``uv sync --extra compiler``.
"""
