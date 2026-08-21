import type { Metadata } from "next";
import { Console } from "@/components/Console";

export const metadata: Metadata = {
  title: "Console — HAVEN",
  description:
    "Predicted alertness against the next safety-critical task, the procedure that governs it, and the clause-by-clause verdict behind the citation.",
};

export default function Page() {
  return <Console />;
}
