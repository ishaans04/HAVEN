"use client";

/**
 * The horizon of a planet, from orbit, at night.
 *
 * Procedural for the same reasons the console's dial is: it stays sharp at any
 * width, weighs nothing, and needs no image pipeline behind a static export.
 * The city lights and the cloud banks come out of a seeded PRNG, so the view
 * from this window is the same in every build of the same commit.
 *
 * The optics are the point. A limb seen from orbit is not a line — it is a
 * hairline of lit atmosphere with a blue haze standing off it, brightest where
 * the terminator is and fading around the curve. Three stacked arcs at falling
 * opacity do more for that than any amount of blur on one.
 */

function prng(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const W = 1440;
const H = 620;
// A sphere far larger than the frame, so the frame only ever catches its top.
const CX = 720;
const CY = 1560;
const R = 1330;
const HORIZON = CY - R; // y = 230

/** Where the surface sits directly below a given x. */
const surfaceY = (x: number) => CY - Math.sqrt(Math.max(0, R * R - (x - CX) ** 2));

/** City lights, clustered rather than scattered — populations are not uniform. */
const LIGHTS = (() => {
  const random = prng(4242);
  const out: { x: number; y: number; r: number; o: number }[] = [];
  for (let cluster = 0; cluster < 26; cluster += 1) {
    const cx = random() * W;
    const cy = surfaceY(cx) + 14 + random() * 300;
    const count = 4 + Math.floor(random() * 16);
    for (let i = 0; i < count; i += 1) {
      const x = cx + (random() - 0.5) * 130;
      const y = cy + (random() - 0.5) * 90;
      if (y < surfaceY(x) + 6 || y > H) continue;
      out.push({
        x: Math.round(x * 10) / 10,
        y: Math.round(y * 10) / 10,
        r: Math.round((0.5 + random() * 1.5) * 100) / 100,
        o: Math.round((0.25 + random() * 0.7) * 100) / 100,
      });
    }
  }
  return out;
})();

/** Cloud banks, following the curve rather than lying flat across it. */
const CLOUDS = (() => {
  const random = prng(99);
  return Array.from({ length: 14 }, () => {
    const x = random() * W;
    return {
      x: Math.round(x),
      y: Math.round(surfaceY(x) + 20 + random() * 240),
      rx: Math.round(70 + random() * 190),
      ry: Math.round(8 + random() * 22),
      o: Math.round((0.05 + random() * 0.1) * 100) / 100,
    };
  });
})();

export function PlanetLimb({ className }: { className?: string }) {
  return (
    <div className={className} aria-hidden>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMax slice"
        className="h-full w-full"
      >
        <defs>
          <radialGradient id="pl-surface" cx="50%" cy="100%" r="70%">
            <stop offset="0%" stopColor="#0d1c38" />
            <stop offset="55%" stopColor="#071023" />
            <stop offset="100%" stopColor="#04060f" />
          </radialGradient>
          <linearGradient id="pl-haze" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="var(--atmo)" stopOpacity="0.5" />
            <stop offset="55%" stopColor="var(--atmo)" stopOpacity="0.13" />
            <stop offset="100%" stopColor="var(--atmo)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="pl-rim" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(160,215,255,0.15)" />
            <stop offset="26%" stopColor="rgba(214,240,255,0.95)" />
            <stop offset="58%" stopColor="rgba(255,236,205,0.8)" />
            <stop offset="100%" stopColor="rgba(160,190,255,0.12)" />
          </linearGradient>
          <clipPath id="pl-body">
            <circle cx={CX} cy={CY} r={R} />
          </clipPath>
          <filter id="pl-bloom" x="-20%" y="-40%" width="140%" height="200%">
            <feGaussianBlur stdDeviation="18" />
          </filter>
          <filter id="pl-soft" x="-30%" y="-60%" width="160%" height="240%">
            <feGaussianBlur stdDeviation="9" />
          </filter>
          <filter id="pl-lights" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.1" />
          </filter>
        </defs>

        {/* The haze standing off the limb, painted before the body so the body
            crops its lower half cleanly. */}
        <ellipse
          cx={CX}
          cy={HORIZON + 128}
          rx={R * 1.02}
          ry={150}
          fill="url(#pl-haze)"
          filter="url(#pl-bloom)"
          opacity={0.85}
        />

        {/* The body. */}
        <g clipPath="url(#pl-body)">
          <rect x="0" y={HORIZON - 4} width={W} height={H - HORIZON + 8} fill="url(#pl-surface)" />
          {CLOUDS.map((c, i) => (
            <ellipse
              key={`c${i}`}
              cx={c.x}
              cy={c.y}
              rx={c.rx}
              ry={c.ry}
              fill="#9fd0ff"
              opacity={c.o}
              filter="url(#pl-soft)"
            />
          ))}
          <g filter="url(#pl-lights)">
            {LIGHTS.map((l, i) => (
              <circle key={`l${i}`} cx={l.x} cy={l.y} r={l.r} fill="var(--city)" opacity={l.o} />
            ))}
          </g>
          {/* Airglow along the inside of the limb. */}
          <ellipse
            cx={CX}
            cy={HORIZON + 26}
            rx={R}
            ry={30}
            fill="rgba(150,215,255,0.22)"
            filter="url(#pl-soft)"
          />
        </g>

        {/* The hairline itself, twice: a soft pass for the bloom and a sharp one
            over it, because a single stroke reads as a drawn line. */}
        <circle
          cx={CX}
          cy={CY}
          r={R}
          fill="none"
          stroke="url(#pl-rim)"
          strokeWidth={7}
          opacity={0.45}
          filter="url(#pl-bloom)"
        />
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="url(#pl-rim)" strokeWidth={1.6} />
      </svg>
    </div>
  );
}
