"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { BookOpen, ChevronDown, X } from "lucide-react";
import { fetchProcedures } from "@/lib/api";
import type { ProcedureSummary } from "@/lib/types";
import { Tag } from "./ui";

/**
 * The corpus, readable.
 *
 * `GET /api/procedures` has existed since v1 and nothing ever called it, which
 * meant the rulebook every recommendation cites was invisible unless you read
 * the source. That is a strange gap in a system whose case rests on citing
 * procedure rather than asserting conclusions: a citation an operator cannot
 * look up is not much of a citation.
 *
 * Two things it shows that a plain list would not.
 *
 * **Provenance.** Which rules were extracted from a real document and which were
 * written for this prototype. A corpus that cannot say is not one anybody should
 * reason over, and this is the surface where that admission belongs.
 *
 * **The near-misses.** The passages that exist to be rejected are labelled as
 * such. Seeing them is what makes the discrimination case legible — the corpus
 * is adversarial by construction, and hiding that would make the reasoning look
 * easier than it is.
 */
export function ProcedureBrowser({ onClose }: { onClose: () => void }) {
  const [procedures, setProcedures] = useState<ProcedureSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    fetchProcedures()
      .then(setProcedures)
      .catch((e: Error) => setError(e.message));
  }, []);

  const byDoc = new Map<string, ProcedureSummary[]>();
  for (const procedure of procedures ?? []) {
    byDoc.set(procedure.doc, [...(byDoc.get(procedure.doc) ?? []), procedure]);
  }

  const extracted = (procedures ?? []).filter((p) => p.provenance === "extracted").length;
  const total = procedures?.length ?? 0;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-black/70 p-4 backdrop-blur-sm">
      <div className="hv-panel my-8 w-full max-w-4xl">
        <header className="flex items-start gap-3 border-b border-[var(--hv-line)] px-4 py-3">
          <BookOpen size={16} className="mt-0.5 shrink-0 text-[color:var(--hv-accent)]" />
          <div className="min-w-0 flex-1">
            <h2 className="text-[13px] font-semibold">The procedure corpus</h2>
            <p className="mt-0.5 text-[11px] leading-snug text-[var(--hv-muted)]">
              Every rule the reasoning tier may cite. Near-misses are included on purpose — the
              corpus is adversarial by construction, and rejecting them is the judgement.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded border border-[var(--hv-line-bright)] p-1 text-[var(--hv-muted)] transition-colors hover:text-[var(--hv-text)]"
          >
            <X size={13} />
          </button>
        </header>

        {error ? (
          <p className="p-6 text-[12px] text-[color:var(--hv-degraded)]">{error}</p>
        ) : !procedures ? (
          <p className="p-6 text-[12px] text-[var(--hv-muted)]">Loading the corpus…</p>
        ) : (
          <>
            <div className="border-b border-[var(--hv-line)] px-4 py-2">
              <span className="mono text-[10px] text-[var(--hv-dim)]">
                {total} passages across {byDoc.size} documents · {extracted} extracted from source
                documents, {total - extracted} written for this prototype
              </span>
            </div>

            <div className="max-h-[65vh] overflow-auto p-4">
              {Array.from(byDoc.entries()).map(([doc, passages]) => (
                <section key={doc} className="mb-5 last:mb-0">
                  <div className="hv-zone-label mb-2">{doc}</div>
                  <ul className="space-y-1.5">
                    {passages.map((procedure: ProcedureSummary) => {
                      const open = expanded === procedure.passage_id;
                      return (
                        <li
                          key={procedure.passage_id}
                          className="rounded border border-[var(--hv-line)] bg-[var(--hv-panel-raised)]"
                        >
                          <button
                            onClick={() => setExpanded(open ? null : procedure.passage_id)}
                            className="flex w-full items-start gap-2 px-3 py-2 text-left"
                          >
                            <span className="mono shrink-0 text-[10px] text-[var(--hv-dim)]">
                              §{procedure.section}
                            </span>
                            <span className="min-w-0 flex-1 text-[12px] leading-snug">
                              {procedure.title}
                            </span>
                            <span className="flex shrink-0 items-center gap-1.5">
                              {procedure.near_miss_note ? <Tag tone="warn">near-miss</Tag> : null}
                              {!procedure.prescribes ? (
                                <Tag tone="neutral">no action</Tag>
                              ) : null}
                              <Tag tone={procedure.provenance === "extracted" ? "good" : "neutral"}>
                                {procedure.provenance}
                              </Tag>
                              <ChevronDown
                                size={12}
                                className={clsx(
                                  "text-[var(--hv-dim)] transition-transform",
                                  open && "rotate-180",
                                )}
                              />
                            </span>
                          </button>

                          {open ? (
                            <div className="border-t border-[var(--hv-line)] px-3 py-2.5">
                              <p className="text-[11px] leading-relaxed text-[var(--hv-text)]">
                                {procedure.text}
                              </p>

                              {procedure.near_miss_note ? (
                                <p className="mt-2 rounded border border-[color:var(--hv-watch)]/40 bg-[color:var(--hv-watch)]/[0.06] px-2 py-1.5 text-[10px] leading-snug text-[color:var(--hv-watch)]">
                                  Retrieved on purpose, and must be rejected:{" "}
                                  {procedure.near_miss_note}
                                </p>
                              ) : null}

                              <dl className="mono mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[10px]">
                                <dt className="text-[var(--hv-dim)]">applies to</dt>
                                <dd className="text-[var(--hv-muted)]">
                                  {procedure.task_types.join(", ") || "—"}
                                </dd>
                                <dt className="text-[var(--hv-dim)]">prescribes</dt>
                                <dd className="text-[var(--hv-muted)]">
                                  {procedure.prescribes ?? "nothing — it cannot ground a recommendation"}
                                </dd>
                                <dt className="text-[var(--hv-dim)]">source</dt>
                                <dd className="text-[var(--hv-muted)]">{procedure.source}</dd>
                                {procedure.reviewed_by ? (
                                  <>
                                    <dt className="text-[var(--hv-dim)]">reviewed by</dt>
                                    <dd className="text-[var(--hv-muted)]">{procedure.reviewed_by}</dd>
                                  </>
                                ) : null}
                              </dl>
                            </div>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
