"use client";

import { useEffect, useRef, useState } from "react";
import { useMotionOK } from "@/lib/motion";

/**
 * The ISS, in silhouette.
 *
 * Drawn in screen space at a fixed size, because it is a marker: scaling it
 * with distance would make it vanish at the far side of the orbit, and the
 * point of the thing is knowing where the crew are. Proportions follow the real
 * station — a long pressurised spine, a truss square across it, four array
 * pairs outboard — at the smallest scale where that reads as the ISS and not as
 * a generic satellite.
 *
 * `lit` decides the array colour: gold in sunlight, cold blue in eclipse, which
 * is the same fact the sunrise counter is counting.
 */
function drawStation(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  heading: number,
  dpr: number,
  alpha: number,
  lit: boolean,
) {
  const u = 1.5 * dpr; // one unit
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(heading);
  ctx.globalAlpha = alpha;

  const array = lit ? "rgba(226,170,96,0.95)" : "rgba(126,158,196,0.75)";
  const metal = "rgba(232,238,244,0.95)";

  // Truss: the long boom the arrays hang off, square across the flight path.
  ctx.strokeStyle = metal;
  ctx.lineWidth = 0.9 * dpr;
  ctx.beginPath();
  ctx.moveTo(0, -5.2 * u);
  ctx.lineTo(0, 5.2 * u);
  ctx.stroke();

  // Four solar arrays, two per side.
  ctx.fillStyle = array;
  for (const sy of [-1, 1]) {
    for (const off of [2.4, 4.0]) {
      ctx.fillRect(-2.5 * u, sy * off * u - 0.62 * u, 5 * u, 1.24 * u);
    }
  }

  // Pressurised modules along the direction of travel.
  ctx.fillStyle = metal;
  ctx.fillRect(-3.1 * u, -0.85 * u, 6.2 * u, 1.7 * u);
  // Radiators.
  ctx.fillStyle = "rgba(190,205,220,0.6)";
  ctx.fillRect(-0.5 * u, -2.1 * u, 1 * u, 4.2 * u);

  ctx.restore();
}

/**
 * Earth, actually rendered.
 *
 * What was here before was a stroked SVG arc with a gradient behind it — the
 * shape every space demo reaches for, and a fake: nothing about it knew where
 * the sun was. This is the real mechanism, and it is affordable, so the rule
 * says build it.
 *
 * Everything below is computed per pixel, per frame, from a sun direction:
 *
 *   · analytic ray–sphere intersection, so the silhouette is a real horizon
 *   · continents from domain-warped fBm — no texture, no asset, no network
 *   · a real terminator: `dot(normal, sun)` with a soft penumbra, which means
 *     the day/night line curves correctly across the limb and moves as the
 *     planet turns on its real 23.44° axial tilt
 *   · city lights that exist only where there is land and only after dark
 *   · specular sheen on water and not on land, because water is what shines
 *   · atmosphere weighted towards blue at grazing angles, which is the reason
 *     the real rim is blue
 *
 * ## Why a planet at all
 *
 * Because the terminator is the subject. A crew member in low orbit crosses it
 * roughly sixteen times a day, and a body clock that gets sixteen sunrises is
 * the entire problem HAVEN exists to reason about. The orbit drawn over the
 * globe is a genuine 51.64° inclined circle at a real altitude, sampled and
 * projected through the same camera, occluded where it passes behind the
 * sphere. The sunrise counter the page quotes is incremented by that orbit
 * actually crossing the terminator — the number is produced, not asserted.
 *
 * ## Verification
 *
 * `requestAnimationFrame` runs at a fraction of a hertz in a background tab,
 * which makes wall-clock waits useless for checking that any of this moves.
 * `window.__havenEarth` exposes a synchronous `tick(seconds)` and a state
 * readout so the simulation can be stepped and asserted deterministically.
 */

const VERT = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const FRAG = `
precision highp float;

uniform vec2  uRes;      // canvas size, device pixels
uniform vec2  uCenter;   // sphere centre, device pixels
uniform float uRadius;   // sphere radius, device pixels
uniform float uSpin;     // rotation about the polar axis, radians
uniform float uLat;      // camera latitude, radians — dragged vertically
uniform float uFlash;    // 0..1, decays after the station crosses into daylight
uniform vec3  uSun;      // unit vector towards the sun, view space
uniform float uTime;

const float TILT = 0.40910518; // 23.44 degrees, radians

/* ---- value noise ------------------------------------------------------- */

float hash(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash(i + vec3(0,0,0)), hash(i + vec3(1,0,0)), f.x),
        mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
    mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
        mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y),
    f.z);
}

float fbm(vec3 p, int oct) {
  float a = 0.5, s = 0.0;
  for (int i = 0; i < 7; i++) {
    if (i >= oct) break;
    s += a * noise(p);
    p *= 2.02;
    a *= 0.5;
  }
  return s;
}

mat3 rotY(float a) {
  float c = cos(a), s = sin(a);
  return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c);
}
mat3 rotX(float a) {
  float c = cos(a), s = sin(a);
  return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c);
}

void main() {
  vec2 d = (gl_FragCoord.xy - uCenter) / uRadius;
  float r2 = dot(d, d);

  vec3 col = vec3(0.0);
  float alpha = 0.0;

  /* ---- atmosphere, outside the disc ------------------------------------
     Rayleigh scattering falls off with distance from the limb and is far
     stronger where the line of sight grazes the most air. Weighting it
     towards blue is not a stylistic choice; it is why the real one is blue. */
  if (r2 > 1.0) {
    float r = sqrt(r2);
    float halo = exp(-(r - 1.0) * 9.0);
    // Only the lit side has air to scatter light.
    vec3 n = vec3(d, 0.0);
    float lit = smoothstep(-0.42, 0.55, dot(normalize(vec3(d, 0.35)), uSun));
    vec3 sky = vec3(0.30, 0.56, 1.0);
    // A sunrise brightens the air on the day side and warms it, which is what
    // a sunrise is. Driven by the same crossing that increments the counter.
    vec3 dawn = mix(sky, vec3(1.0, 0.62, 0.30), uFlash * 0.55);
    float gain = 1.0 + uFlash * 0.85;
    col = dawn * halo * lit * 0.95 * gain;
    alpha = halo * lit * 0.95 * gain;
    gl_FragColor = vec4(col, clamp(alpha, 0.0, 1.0));
    return;
  }

  /* ---- the sphere ------------------------------------------------------ */
  float z = sqrt(max(0.0, 1.0 - r2));
  vec3 n = vec3(d, z);                       // surface normal, view space

  // Into planet space: undo the viewing latitude, then the axial tilt, then
  // the spin. Rotating the sample point rather than the sun keeps the lighting
  // fixed in view space, so dragging moves the planet under the sun the way it
  // should rather than dragging the terminator along with it.
  vec3 p = rotX(-uLat) * n;
  p = rotX(-TILT) * p;
  p = rotY(-uSpin) * p;

  /* ---- continents ------------------------------------------------------
     Domain warping is what stops fBm reading as clouds-on-a-ball: warping the
     lookup with another fBm produces coastlines with inlets and peninsulas
     rather than soft blobs. */
  vec3 w = vec3(fbm(p * 1.7 + 11.0, 4), fbm(p * 1.7 + 27.0, 4), fbm(p * 1.7 + 41.0, 4));
  float h = fbm(p * 2.1 + w * 1.35, 6);

  float land = smoothstep(0.505, 0.545, h);
  float shelf = smoothstep(0.470, 0.510, h);   // shallow water round the coasts

  // Ice, by latitude, with a ragged edge.
  float lat = abs(p.y);
  float ice = smoothstep(0.70, 0.88, lat + (h - 0.5) * 0.55);

  // Deserts sit in the mid latitudes; green belts nearer the equator.
  float arid = smoothstep(0.14, 0.42, abs(p.y)) * (1.0 - smoothstep(0.55, 0.78, abs(p.y)));
  vec3 vegetation = mix(vec3(0.10, 0.20, 0.11), vec3(0.16, 0.15, 0.09), arid);
  vec3 deep = vec3(0.012, 0.035, 0.085);
  vec3 shallow = vec3(0.03, 0.10, 0.17);

  vec3 albedo = mix(deep, shallow, shelf * (1.0 - land));
  albedo = mix(albedo, vegetation, land);
  albedo = mix(albedo, vec3(0.72, 0.80, 0.86), ice);

  /* ---- cloud deck ------------------------------------------------------
     A second field on its own slower rotation, so weather does not look
     painted onto the ground. */
  vec3 cp = rotY(-uSpin * 1.18 - uTime * 0.004) * (rotX(-TILT) * (rotX(-uLat) * n));
  float cloud = smoothstep(0.52, 0.72, fbm(cp * 2.6 + vec3(0.0, uTime * 0.006, 0.0), 5));
  cloud *= 0.82;

  /* ---- lighting --------------------------------------------------------
     The terminator. Everything the page claims about sunrises comes from
     this one dot product. */
  float ndl = dot(n, uSun);
  float day = smoothstep(-0.09, 0.22, ndl);

  // Limb darkening: the horizon is dimmer because you are looking through
  // more atmosphere and at a steeper angle.
  float limb = pow(max(z, 0.0), 0.34);

  vec3 sun = vec3(1.0, 0.96, 0.90);
  vec3 lit = (albedo * (1.0 - cloud) + vec3(0.62, 0.66, 0.72) * cloud) * day * limb;

  /* ---- specular, water only -------------------------------------------- */
  vec3 view = vec3(0.0, 0.0, 1.0);
  vec3 hv = normalize(uSun + view);
  float spec = pow(max(dot(n, hv), 0.0), 46.0) * (1.0 - land) * (1.0 - cloud) * day;
  lit += sun * spec * 0.42;

  /* ---- night side ------------------------------------------------------
     Cities cluster: a high-frequency field thresholded hard, gated on land,
     and thinned towards the poles where nobody lives. */
  float nightMask = 1.0 - day;
  float pop = fbm(p * 26.0, 3);
  float coastal = shelf - land * 0.35;
  float cities = smoothstep(0.60, 0.78, pop) * land
               * (1.0 - smoothstep(0.55, 0.80, lat))
               * (0.55 + 0.45 * smoothstep(0.0, 0.4, coastal));
  cities *= (1.0 - cloud * 0.75) * nightMask * limb;
  vec3 lampLight = vec3(1.0, 0.72, 0.36);

  // A trace of airglow so the dark side is not a hole in the page.
  vec3 nightGround = albedo * 0.030 * nightMask;

  col = lit + nightGround + lampLight * cities * 1.25;

  /* ---- atmosphere on the disc ------------------------------------------ */
  float rim = pow(1.0 - z, 3.4);
  col += vec3(0.26, 0.50, 0.95) * rim * day * (1.15 + uFlash * 1.1);
  // Dusk runs warm right at the terminator, where light travels furthest.
  float dusk = exp(-abs(ndl) * 13.0) * (1.0 - rim * 0.5);
  col += vec3(1.0, 0.44, 0.16) * dusk * 0.30;

  // Feather the very edge so the disc does not alias against the page.
  float edge = smoothstep(1.0, 1.0 - (1.6 / uRadius), sqrt(r2));
  gl_FragColor = vec4(col, edge);
}
`;

type Placement = {
  /** Sphere centre x, as a fraction of the canvas width. */
  cx: number;
  /** Sphere radius, as a fraction of the canvas width. */
  r: number;
  /**
   * Sphere centre y, as a fraction of the canvas height, measured downwards
   * from the top. May sit outside the box.
   */
  cy?: number;
  /**
   * Where the top of the sphere should land, as a fraction of the canvas
   * height. Takes precedence over `cy`. Prefer this for a horizon: the radius
   * is a fraction of the *width*, so fixing the centre against the height
   * makes the result depend on the aspect ratio, and a viewport that is wider
   * or shorter than expected pushes the whole sphere out of frame.
   */
  topAt?: number;
};

export function Earth({
  className,
  placement,
  /** Draw the station and its ground track. */
  orbit = true,
  /** Let the reader grab and spin it. Off for the console's backdrop. */
  interactive = false,
  /**
   * Extra rotation from outside, in radians — the landing feeds scroll into
   * this so the planet turns as you read down the page.
   */
  spinBias = 0,
  onSunrise,
  /** Fires the first time somebody actually grabs it. */
  onGrab,
}: {
  className?: string;
  placement: Placement;
  orbit?: boolean;
  interactive?: boolean;
  spinBias?: number;
  onSunrise?: (count: number) => void;
  onGrab?: () => void;
}) {
  const glCanvas = useRef<HTMLCanvasElement>(null);
  const overlay = useRef<HTMLCanvasElement>(null);
  const motionOK = useMotionOK();
  const [failed, setFailed] = useState(false);
  const sunriseCb = useRef(onSunrise);
  sunriseCb.current = onSunrise;
  // Read inside the loop rather than closed over, so a scroll does not tear
  // down and rebuild the whole GL context.
  const bias = useRef(spinBias);
  bias.current = spinBias;
  const grabCb = useRef(onGrab);
  grabCb.current = onGrab;

  useEffect(() => {
    const canvas = glCanvas.current;
    const over = overlay.current;
    if (!canvas || !over) return;

    const gl =
      (canvas.getContext("webgl", { alpha: true, antialias: false, premultipliedAlpha: false }) as
        | WebGLRenderingContext
        | null) ?? null;
    if (!gl) {
      setFailed(true);
      return;
    }

    /* ---- programme ----------------------------------------------------- */
    const compile = (type: number, src: string) => {
      const sh = gl.createShader(type)!;
      gl.shaderSource(sh, src);
      gl.compileShader(sh);
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
        throw new Error(gl.getShaderInfoLog(sh) ?? "shader compile failed");
      }
      return sh;
    };

    let program: WebGLProgram;
    try {
      program = gl.createProgram()!;
      gl.attachShader(program, compile(gl.VERTEX_SHADER, VERT));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(program) ?? "link failed");
      }
    } catch {
      setFailed(true);
      return;
    }

    gl.useProgram(program);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(program, "aPos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    const U = {
      res: gl.getUniformLocation(program, "uRes"),
      center: gl.getUniformLocation(program, "uCenter"),
      radius: gl.getUniformLocation(program, "uRadius"),
      spin: gl.getUniformLocation(program, "uSpin"),
      lat: gl.getUniformLocation(program, "uLat"),
      flash: gl.getUniformLocation(program, "uFlash"),
      sun: gl.getUniformLocation(program, "uSun"),
      time: gl.getUniformLocation(program, "uTime"),
    };

    /* ---- geometry of the box ------------------------------------------- */
    let dpr = 1;
    let W = 0;
    let H = 0;
    let cx = 0;
    let cy = 0;
    let radius = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = Math.round(rect.width * dpr);
      H = Math.round(rect.height * dpr);
      canvas.width = W;
      canvas.height = H;
      over.width = W;
      over.height = H;
      cx = placement.cx * W;
      radius = placement.r * W;
      // GL's y runs up the screen; the placement is given in CSS terms.
      const fromTop =
        placement.topAt !== undefined
          ? placement.topAt * H + radius
          : (placement.cy ?? 0.5) * H;
      cy = H - fromTop;
      gl.viewport(0, 0, W, H);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    /* ---- the simulation -------------------------------------------------
       One planet-day is compressed to 96 seconds so the terminator visibly
       moves; the orbit keeps its true ratio to that day, so the station still
       makes ~15.5 revolutions per rotation and the sunrise count stays real. */
    const DAY = 96;
    const ORBITS_PER_DAY = 86400 / 5580; // ISS: ~92.9 min period
    const INCLINATION = (51.64 * Math.PI) / 180;
    const ALT = 1.062; // 420 km above a 6371 km radius

    const sim = {
      t: 0,
      spin: 0,
      sunrises: 0,
      lastLit: null as boolean | null,
      station: { x: 0, y: 0, z: 0 },
      sun: { x: 0.82, y: 0.16, z: 0.55 },
      // What the reader has done to it.
      userSpin: 0,
      userLat: 0,
      spinVel: 0,
      latVel: 0,
      dragging: false,
      // Decays after each sunrise.
      flash: 0,
    };

    const stationAt = (t: number) => {
      const a = (t / DAY) * ORBITS_PER_DAY * Math.PI * 2;
      // A circular orbit in its own plane, then inclined, then precessed
      // slowly so successive passes do not retrace one line.
      const px = Math.cos(a) * ALT;
      const pz = Math.sin(a) * ALT;
      const y = pz * Math.sin(INCLINATION);
      const z0 = pz * Math.cos(INCLINATION);
      const node = t * 0.0038;
      return {
        x: px * Math.cos(node) - z0 * Math.sin(node),
        y,
        z: px * Math.sin(node) + z0 * Math.cos(node),
      };
    };

    const step = (dt: number) => {
      sim.t += dt;

      // Spin-down. Not a tuned easing curve: a exp(-k·t) decay is what a thing
      // with angular momentum and a little drag actually does, and it stays
      // frame-rate independent when the tab throttles.
      if (!sim.dragging) {
        const damp = Math.exp(-2.1 * dt);
        sim.spinVel *= damp;
        sim.latVel *= damp;
        sim.userSpin += sim.spinVel * dt;
        sim.userLat += sim.latVel * dt;
      }
      // Latitude is bounded: past the poles the globe reads as broken.
      sim.userLat = Math.max(-0.85, Math.min(0.85, sim.userLat));
      sim.flash = Math.max(0, sim.flash - dt * 1.5);
      sim.spin = ((sim.t / DAY) * Math.PI * 2) % (Math.PI * 2);

      // The sun swings slowly through the view so the terminator sweeps the
      // visible face rather than sitting still at one longitude.
      const sa = sim.t * 0.0125;
      const len = Math.hypot(Math.cos(sa), 0.17, Math.sin(sa) * 0.55 + 0.5);
      sim.sun = {
        x: Math.cos(sa) / len,
        y: 0.17 / len,
        z: (Math.sin(sa) * 0.55 + 0.5) / len,
      };

      const s = stationAt(sim.t);
      sim.station = s;
      // A real sunrise: the station crossing from shadow into light.
      const lit = (s.x * sim.sun.x + s.y * sim.sun.y + s.z * sim.sun.z) > 0;
      if (sim.lastLit === false && lit) {
        sim.sunrises += 1;
        sim.flash = 1;
        sunriseCb.current?.(sim.sunrises);
      }
      sim.lastLit = lit;
    };

    const drawGL = () => {
      if (!W || !H) return;
      gl.uniform2f(U.res, W, H);
      gl.uniform2f(U.center, cx, cy);
      gl.uniform1f(U.radius, radius);
      gl.uniform1f(U.spin, sim.spin + sim.userSpin + bias.current);
      gl.uniform1f(U.lat, sim.userLat);
      gl.uniform1f(U.flash, sim.flash);
      gl.uniform3f(U.sun, sim.sun.x, sim.sun.y, sim.sun.z);
      gl.uniform1f(U.time, sim.t);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };

    /* ---- the orbit, projected through the same camera ------------------- */
    const ctx = over.getContext("2d");
    const drawOrbit = () => {
      if (!ctx || !orbit) return;
      ctx.clearRect(0, 0, W, H);
      const toPx = (p: { x: number; y: number; z: number }) => ({
        x: cx + p.x * radius,
        // Canvas y runs down; the sim's y runs up.
        y: H - (cy + p.y * radius),
        z: p.z,
      });

      // Sample a full revolution and draw it in two passes so the half behind
      // the planet is genuinely occluded rather than drawn on top of it.
      const pts: { x: number; y: number; z: number; behind: boolean }[] = [];
      const N = 220;
      for (let i = 0; i <= N; i++) {
        const p = stationAt(sim.t + (i / N) * (DAY / ORBITS_PER_DAY));
        const s = toPx(p);
        const inDisc = Math.hypot(s.x - cx, s.y - (H - cy)) < radius;
        pts.push({ x: s.x, y: s.y, z: s.z, behind: s.z < 0 && inDisc });
      }

      for (const behind of [true, false]) {
        ctx.beginPath();
        let drawing = false;
        for (const p of pts) {
          if (p.behind !== behind) {
            drawing = false;
            continue;
          }
          if (!drawing) {
            ctx.moveTo(p.x, p.y);
            drawing = true;
          } else ctx.lineTo(p.x, p.y);
        }
        ctx.strokeStyle = behind ? "rgba(148,178,206,0.16)" : "rgba(196,220,240,0.42)";
        ctx.lineWidth = Math.max(1, dpr);
        ctx.stroke();
      }

      // The station.
      const s = toPx(sim.station);
      const occluded = s.z < 0 && Math.hypot(s.x - cx, s.y - (H - cy)) < radius;
      const lit =
        sim.station.x * sim.sun.x + sim.station.y * sim.sun.y + sim.station.z * sim.sun.z > 0;
      const a = occluded ? 0.2 : 1;

      // Which way is it going? Sample a moment ahead and point the hull along
      // the screen-space difference, so the arrays sit square to the track.
      const ahead = toPx(stationAt(sim.t + 6));
      const heading = Math.atan2(ahead.y - s.y, ahead.x - s.x);

      const glow = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, 18 * dpr);
      const hue = lit ? "232,186,126" : "150,180,215";
      glow.addColorStop(0, `rgba(${hue},${0.5 * a})`);
      glow.addColorStop(1, `rgba(${hue},0)`);
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(s.x, s.y, 18 * dpr, 0, Math.PI * 2);
      ctx.fill();

      drawStation(ctx, s.x, s.y, heading, dpr, a, lit);
    };

    const render = () => {
      drawGL();
      drawOrbit();
    };

    /* ---- drive ---------------------------------------------------------- */
    let raf = 0;
    let last = performance.now();
    let running = true;

    const frame = (now: number) => {
      if (!running) return;
      // Clamp: a background tab can hand back a multi-second delta, which
      // would teleport the station and bank a fistful of false sunrises.
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      if (motionOK) step(dt);
      render();
      raf = requestAnimationFrame(frame);
    };

    // Warm start, so the first painted frame is a lit planet rather than a
    // black disc with the sun still at its initial guess.
    for (let i = 0; i < 60; i++) step(0.25);
    sim.sunrises = 0;
    render();
    raf = requestAnimationFrame(frame);

    /* ---- grab it -------------------------------------------------------
       Real 3D you cannot touch is indistinguishable from a video, so the
       overlay takes pointer events and hands them to the same spin the shader
       already uses. Velocity is kept in radians per second and handed to the
       inertia in `step`, which is why a throw keeps going after release. */
    const cleanupDrag: (() => void)[] = [];
    if (interactive) {
      over.style.pointerEvents = "auto";
      over.style.cursor = "grab";
      over.style.touchAction = "pan-y"; // never trap the page scroll

      let id: number | null = null;
      let lastX = 0;
      let lastY = 0;
      let lastT = 0;

      const inside = (e: PointerEvent) => {
        const r = over.getBoundingClientRect();
        const px = (e.clientX - r.left) * (W / r.width);
        const py = (r.bottom - e.clientY) * (H / r.height);
        return Math.hypot(px - cx, py - cy) < radius * 1.08;
      };

      const down = (e: PointerEvent) => {
        if (!inside(e)) return;
        id = e.pointerId;
        over.setPointerCapture(id);
        sim.dragging = true;
        grabCb.current?.();
        sim.spinVel = 0;
        sim.latVel = 0;
        lastX = e.clientX;
        lastY = e.clientY;
        lastT = performance.now();
        over.style.cursor = "grabbing";
      };

      const move = (e: PointerEvent) => {
        if (id !== e.pointerId) {
          over.style.cursor = inside(e) ? "grab" : "default";
          return;
        }
        const now = performance.now();
        const dt = Math.max((now - lastT) / 1000, 1 / 240);
        const r = over.getBoundingClientRect();
        // A drag across the sphere's width is a half turn: the grabbed point
        // stays roughly under the finger.
        const dx = ((e.clientX - lastX) / r.width) * Math.PI * 2.4;
        const dy = ((e.clientY - lastY) / r.height) * Math.PI * 1.1;
        sim.userSpin += dx;
        sim.userLat = Math.max(-0.85, Math.min(0.85, sim.userLat + dy));
        sim.spinVel = dx / dt;
        sim.latVel = dy / dt;
        lastX = e.clientX;
        lastY = e.clientY;
        lastT = now;
        if (!motionOK) render(); // no rAF loop to pick it up
      };

      const up = (e: PointerEvent) => {
        if (id !== e.pointerId) return;
        // A pointer parked for a moment before release has thrown nothing.
        if (performance.now() - lastT > 90) {
          sim.spinVel = 0;
          sim.latVel = 0;
        }
        try {
          over.releasePointerCapture(id);
        } catch {
          /* already gone */
        }
        id = null;
        sim.dragging = false;
        over.style.cursor = "grab";
      };

      over.addEventListener("pointerdown", down);
      over.addEventListener("pointermove", move);
      over.addEventListener("pointerup", up);
      over.addEventListener("pointercancel", up);
      cleanupDrag.push(() => {
        over.removeEventListener("pointerdown", down);
        over.removeEventListener("pointermove", move);
        over.removeEventListener("pointerup", up);
        over.removeEventListener("pointercancel", up);
      });
    }

    // Pause when scrolled away: this is a background flourish, not the app.
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !running) {
          running = true;
          last = performance.now();
          raf = requestAnimationFrame(frame);
        } else if (!entry.isIntersecting && running) {
          running = false;
          cancelAnimationFrame(raf);
        }
      },
      { rootMargin: "120px" },
    );
    io.observe(canvas);

    const onLost = (e: Event) => {
      e.preventDefault();
      running = false;
      cancelAnimationFrame(raf);
      setFailed(true);
    };
    canvas.addEventListener("webglcontextlost", onLost);

    // A synchronous handle for verification: rAF is throttled to a fraction of
    // a hertz in a background tab, so stepping by hand is the only way to
    // assert that any of this actually moves.
    const handle = {
      tick(seconds: number, steps = 30) {
        for (let i = 0; i < steps; i++) step(seconds / steps);
        render();
        return handle.state();
      },
      /** Drag the globe by a screen-space delta, in CSS pixels. */
      drag(dx: number, dy: number) {
        const r = over.getBoundingClientRect();
        sim.userSpin += (dx / r.width) * Math.PI * 2.4;
        sim.userLat = Math.max(
          -0.85,
          Math.min(0.85, sim.userLat + (dy / r.height) * Math.PI * 1.1),
        );
        render();
        return handle.state();
      },
      state: () => ({
        t: +sim.t.toFixed(2),
        spin: +sim.spin.toFixed(4),
        userSpin: +sim.userSpin.toFixed(4),
        userLat: +sim.userLat.toFixed(4),
        spinVel: +sim.spinVel.toFixed(4),
        flash: +sim.flash.toFixed(3),
        interactive,
        sunrises: sim.sunrises,
        station: {
          x: +sim.station.x.toFixed(4),
          y: +sim.station.y.toFixed(4),
          z: +sim.station.z.toFixed(4),
        },
        sun: { x: +sim.sun.x.toFixed(4), y: +sim.sun.y.toFixed(4), z: +sim.sun.z.toFixed(4) },
        altitude: +Math.hypot(sim.station.x, sim.station.y, sim.station.z).toFixed(4),
        orbitsPerDay: +ORBITS_PER_DAY.toFixed(3),
        pixels: { W, H, cx, cy, radius: +radius.toFixed(1) },
      }),
    };
    (window as unknown as Record<string, unknown>).__havenEarth = handle;

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      cleanupDrag.forEach((f) => f());
      io.disconnect();
      ro.disconnect();
      canvas.removeEventListener("webglcontextlost", onLost);
      gl.deleteProgram(program);
      gl.deleteBuffer(buf);
      delete (window as unknown as Record<string, unknown>).__havenEarth;
    };
  }, [placement.cx, placement.cy, placement.r, placement.topAt, orbit, interactive, motionOK]);

  return (
    <div className={className} aria-hidden>
      <canvas
        ref={glCanvas}
        className="absolute inset-0 h-full w-full"
        style={{ opacity: failed ? 0 : 1, transition: "opacity 900ms ease" }}
      />
      <canvas ref={overlay} className="absolute inset-0 h-full w-full" />
      {/* If WebGL is unavailable the page keeps a horizon rather than a hole. */}
      {failed ? (
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(60% 50% at 50% 118%, rgba(60,110,150,0.5), transparent 68%)",
          }}
        />
      ) : null}
    </div>
  );
}
