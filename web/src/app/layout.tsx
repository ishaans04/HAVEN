import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
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
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
