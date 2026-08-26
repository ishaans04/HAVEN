import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

/*
 * IBM Plex, and not for decoration.
 *
 * The console shipped in Geist, which is a fine typeface and the wrong one
 * here: it is Vercel's, it is on every AI product of the last two years, and it
 * is deliberately characterless. A fatigue console for an IBM challenge reading
 * like a Next.js starter is a brand mistake before it is a taste one.
 *
 * Plex is IBM's own, open source under the SIL OFL, and drawn for engineering
 * contexts — the flared stems and the unmistakable `a` and `g` give it a voice
 * Geist declines to have. The mono is the part that earns its place twice: this
 * screen is mostly figures, and Plex Mono was designed to be read as data
 * rather than as code.
 *
 * `next/font/google` downloads and self-hosts at build time, so the static
 * export carries the files and makes no runtime request — the offline path
 * stays a first-class path.
 */
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  // 300 for display settings, 400 body, 500 for the one word that matters,
  // 600 nowhere yet but present so emphasis has somewhere to go.
  weight: ["300", "400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "HAVEN — Fatigue-Aware Safety Co-Pilot",
  description:
    "Human Adaptation & Vitality Enhancement Network. Deterministic fatigue modelling with a grounded, citing, refusing AI reasoning tier.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        {/*
          Marks the document as scripted, before first paint.

          Scroll reveals start hidden, and the class that hides them ships in
          the prerendered HTML — so without this, a reader with scripting
          disabled would get a blank page and no way to un-blank it. The hiding
          rule is scoped to `html.js`, which only exists if the line below ran.
        */}
        <script
          dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('js')" }}
        />
      </head>
      <body className={`${sans.variable} ${mono.variable} antialiased`}>{children}</body>
    </html>
  );
}
