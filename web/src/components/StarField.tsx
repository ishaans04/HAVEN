"use client";

/**
 * The starfield behind everything.
 *
 * Generated rather than shipped: a seeded PRNG lays out the field at module
 * load, so it is identical on every render and in every build, weighs nothing,
 * and needs no image pipeline behind a static export.
 *
 * Two layers at different scales and opacities. A single layer of uniform dots
 * reads as texture; two read as distance, which is the whole point of putting
 * anything back there.
 */

// Mulberry32. Small, fast, and deterministic — the only property that matters
// here is that the sky does not change between two builds of the same commit.
function prng(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Star {
  x: number;
  y: number;
  r: number;
  o: number;
}

function field(seed: number, count: number, rMin: number, rMax: number, oMin: number, oMax: number) {
  const random = prng(seed);
  const stars: Star[] = [];
  for (let i = 0; i < count; i += 1) {
    stars.push({
      x: Math.round(random() * 10000) / 10,
      y: Math.round(random() * 10000) / 10,
      r: Math.round((rMin + random() * (rMax - rMin)) * 100) / 100,
      o: Math.round((oMin + random() * (oMax - oMin)) * 100) / 100,
    });
  }
  return stars;
}

const FAR = field(20260822, 150, 0.35, 0.75, 0.16, 0.48);
const NEAR = field(31415926, 42, 0.7, 1.35, 0.5, 0.95);

export function StarField() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 1000 1000"
        preserveAspectRatio="xMidYMid slice"
      >
        {FAR.map((s, i) => (
          <circle key={`f${i}`} cx={s.x} cy={s.y} r={s.r} fill="#fff" opacity={s.o} />
        ))}
        {NEAR.map((s, i) => (
          <circle key={`n${i}`} cx={s.x} cy={s.y} r={s.r} fill="#e8e4ff" opacity={s.o} />
        ))}
      </svg>
    </div>
  );
}
