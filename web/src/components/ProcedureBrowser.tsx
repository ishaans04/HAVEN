"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { ChevronDown } from "lucide-react";
import { fetchProcedures } from "@/lib/api";
import type { ProcedureSummary } from "@/lib/types";
import { Chip, Label, Sheet, type Tone } from "./ui";

/**
 * The corpus, readable.
 *
 * `GET /api/procedures` existed from v1 and nothing called it, which meant the
 * rulebook every recommendation cites was invisible unless you read the source.
 * That is a strange gap in a system whose case rests on citing procedure rather
 * than asserting conclusions: a citation an operator cannot look up is not much
 * of a citation.
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

  // Only an authoritative requirement — or a prototype rule standing in for one —
  // may ground an action. Guidance and research are retrievable and readable and
  // can never be cited for a recommendation, which is a distinction a reader
  // should see on the row rather than infer from the document name.
  const canPrescribe = (authority: string) =>
    authority === "authoritative" || authority === "prototype";
  const authorityTone = (authority: string): Tone =>
    authority === "authoritative" ? "ok" : canPrescribe(authority) ? "neutral" : "warn";

  return (
    <Sheet
      open
      onClose={onClose}
      title="The rulebook"
      hint={
        <>
          Every passage the reasoning tier may read. Only{" "}
          <span className="text-[var(--ink)]">authoritative</span> requirements may ground an action
          — guidance and research are here to be read and rejected, as are the near-misses. The
          corpus is adversarial by construction, and rejecting is the judgement.
        </>
      }
    >
      {error ? (
        <p className="py-6 text-[13px] text-[var(--bad)]">{error}</p>
      ) : !procedures ? (
        <p className="py-6 text-[13px] text-[var(--ink-2)]">Loading the corpus…</p>
      ) : (
        <>
          <p className="mono border-t border-white/[0.08] py-3 text-[11.5px] text-[var(--ink-3)]">
            {total} passages across {byDoc.size} documents · {extracted} extracted from source
            documents, {total - extracted} written for this prototype
          </p>

          <div className="max-h-[62vh] space-y-5 overflow-auto pr-1">
            {Array.from(byDoc.entries()).map(([doc, passages]) => (
              <section key={doc}>
                <Label className="mb-2">{doc}</Label>
                <ul className="space-y-1.5">
                  {passages.map((procedure) => {
                    const open = expanded === procedure.passage_id;
                    return (
                      <li key={procedure.passage_id} className="glass-2">
                        <button
                          onClick={() => setExpanded(open ? null : procedure.passage_id)}
                          aria-expanded={open}
                          className="flex w-full items-start gap-3 px-4 py-3 text-left"
                        >
                          <span className="mono shrink-0 text-[11.5px] text-[var(--ink-3)]">
                            §{procedure.section}
                          </span>
                          <span className="min-w-0 flex-1 text-[13px] leading-snug text-[var(--ink)]">
                            {procedure.title}
                          </span>
                          <span className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                            {procedure.near_miss_note ? <Chip tone="warn">near-miss</Chip> : null}
                            {!procedure.prescribes ? <Chip tone="neutral">no action</Chip> : null}
                            <Chip tone={authorityTone(procedure.authority)}>
                              {procedure.authority}
                            </Chip>
                            <Chip tone={procedure.provenance === "extracted" ? "ok" : "neutral"}>
                              {procedure.provenance}
                            </Chip>
                            <ChevronDown
                              size={14}
                              className={clsx(
                                "text-[var(--ink-3)] transition-transform duration-300",
                                open && "rotate-180",
                              )}
                            />
                          </span>
                        </button>

                        {open ? (
                          <div className="rise border-t border-white/[0.07] px-4 py-3.5">
                            <p className="text-[13px] leading-relaxed text-[var(--ink-2)]">
                              {procedure.text}
                            </p>

                            {procedure.near_miss_note ? (
                              <p
                                className="mt-3 rounded-[var(--radius-xs)] px-3 py-2 text-[12px] leading-snug text-[var(--warn)]"
                                style={{
                                  background: "rgba(255,207,107,0.08)",
                                  boxShadow: "inset 0 0 0 1px rgba(255,207,107,0.26)",
                                }}
                              >
                                Retrieved on purpose, and must be rejected:{" "}
                                {procedure.near_miss_note}
                              </p>
                            ) : null}

                            <dl className="mono mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11.5px]">
                              <dt className="text-[var(--ink-3)]">applies to</dt>
                              <dd className="text-[var(--ink-2)]">
                                {procedure.task_types.join(", ") || "—"}
                              </dd>
                              <dt className="text-[var(--ink-3)]">prescribes</dt>
                              <dd className="text-[var(--ink-2)]">
                                {procedure.prescribes ??
                                  "nothing — it cannot ground a recommendation"}
                              </dd>
                              <dt className="text-[var(--ink-3)]">source</dt>
                              <dd className="text-[var(--ink-2)]">{procedure.source}</dd>
                              {procedure.reviewed_by ? (
                                <>
                                  <dt className="text-[var(--ink-3)]">reviewed by</dt>
                                  <dd className="text-[var(--ink-2)]">{procedure.reviewed_by}</dd>
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
    </Sheet>
  );
}
