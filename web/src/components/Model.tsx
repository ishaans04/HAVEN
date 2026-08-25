"use client";

import { useEffect, useRef, useState } from "react";
import { useMotionOK } from "@/lib/motion";

/**
 * A glTF model, rendered against plain WebGL.
 *
 * This began as the astronaut and is now shared with the station, because the
 * two need exactly the same thing and nothing more: one mesh, flat material
 * colours, no textures, no animation, no skinning. The alternative was three.js
 * -- and a dropped-in loader is a component every other entrant can ship too,
 * where this is about eighty lines that read precisely the subset in hand.
 *
 * ## What it will and will not do
 *
 * It reads `POSITION`, `NORMAL`, indices and `baseColorFactor`. It honours
 * `byteStride` and shared bufferViews, which is not a detail: both models here
 * interleave position and normal into one view and pack every index accessor
 * into another, and assuming tight packing renders a cloud of shrapnel that
 * still passes a pixel-coverage check.
 *
 * It does not read Draco. Both files are decoded once, offline -- Draco's WASM
 * decoder is around 250 KB, larger than the three.js it would be replacing.
 * See `public/models/CREDITS.md`.
 *
 * ## Imagery, not instrumentation
 *
 * Nothing about the pose or the lighting is derived from crew data, and nothing
 * should be read off either model. That distinction is why the dial's planet
 * was removed rather than dressed up with invented markings: a picture is
 * allowed to be a picture, as long as it never pretends to be a reading.
 */

const VERT = `
attribute vec3 aPos;
attribute vec3 aNrm;
uniform mat4 uProj;
uniform mat4 uView;
uniform mat4 uModel;
uniform mat3 uNormal;
varying vec3 vN;
void main() {
  vN = normalize(uNormal * aNrm);
  gl_Position = uProj * uView * uModel * vec4(aPos, 1.0);
}
`;

const FRAG = `
precision highp float;
uniform vec3 uColor;
varying vec3 vN;

void main() {
  vec3 n = normalize(vN);
  // A key from high and left, the way a hangar light falls, and a dim fill
  // from the other side so the shadow half keeps its shape instead of going
  // flat black against the page.
  vec3 key = normalize(vec3(-0.55, 0.78, 0.62));
  vec3 fill = normalize(vec3(0.7, -0.15, 0.35));
  float kd = max(dot(n, key), 0.0);
  float fd = max(dot(n, fill), 0.0);

  vec3 lit = uColor * (0.16 + 0.86 * kd) + uColor * fd * 0.20;

  // A cool rim, which is what separates a figure from a dark page — blue for
  // the same reason the planet's limb is blue in the section above.
  float rim = pow(1.0 - max(dot(n, vec3(0.0, 0.0, 1.0)), 0.0), 2.6);
  lit += vec3(0.42, 0.60, 0.86) * rim * 0.52;

  // A trace of specular on the key, so the fabric does not read as clay.
  vec3 h = normalize(key + vec3(0.0, 0.0, 1.0));
  lit += vec3(1.0) * pow(max(dot(n, h), 0.0), 34.0) * 0.10;

  gl_FragColor = vec4(lit, 1.0);
}
`;

/** One attribute, described the way WebGL needs to read it. */
interface Attr {
  buffer: WebGLBuffer;
  type: number;
  normalized: boolean;
  /** Bytes between consecutive elements. 0 means tightly packed. */
  stride: number;
  /** Byte offset of the first element within the buffer. */
  offset: number;
}

interface Prim {
  pos: Attr;
  nrm: Attr;
  indices: WebGLBuffer;
  indexType: number;
  indexOffset: number;
  count: number;
  color: [number, number, number];
}

/** glTF component type to [GL enum, bytes per component]. */
const COMPONENT: Record<number, [number, number]> = {
  5120: [0x1400, 1],
  5121: [0x1401, 1],
  5122: [0x1402, 2],
  5123: [0x1403, 2],
  5125: [0x1405, 4],
  5126: [0x1406, 4],
};

/**
 * What the GPU divides a normalized integer attribute by.
 *
 * This exists because of a bug that renders nothing and reports no error. A
 * quantized accessor stores `min`/`max` as the **raw integers** it holds, while
 * `vertexAttribPointer(..., normalized = true)` hands the shader those same
 * values mapped into [-1, 1]. Framing the camera off the raw numbers therefore
 * measured the model as 65,392 units across when the shader sees roughly 2, and
 * parked the camera a hundred thousand units from a figure two units tall:
 * 37,633 triangles drawn, `getError()` clean, and an empty canvas.
 */
const NORMALIZE_DIV: Record<number, number> = {
  5120: 127,
  5121: 255,
  5122: 32767,
  5123: 65535,
};

export function Model({
  src,
  label,
  className,
  /**
   * Radians a second. The suit turns at 0.48 -- three times its first rate,
   * where a forty-second revolution read as a still image with a suspicion of
   * drift. The station is slower, because it is bigger and further away.
   */
  spinRate = 0.48,
  /**
   * Camera distance, as a multiple of the model's longest side. Smaller fills
   * more of the frame. Measured per model rather than guessed: see the note
   * beside the projection below.
   */
  fit = 2.25,
  /** Where the verification handle is published on `window`. */
  handleKey = "__havenModel",
  /** Skipped entirely until the reader is near it. */
  eager = false,
}: {
  src: string;
  /** Described for a screen reader; these are pictures, so say what of. */
  label: string;
  className?: string;
  spinRate?: number;
  fit?: number;
  handleKey?: string;
  eager?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const motionOK = useMotionOK();
  const [failed, setFailed] = useState(false);
  const hostRef = useRef<HTMLDivElement>(null);
  /**
   * Whether the reader is close enough to be worth 540 KB.
   *
   * Two things this deliberately does not use. An IntersectionObserver never
   * fired once here, and `useReveal` — the project's own watcher — schedules
   * its comparison inside `requestAnimationFrame`, which a hidden tab suspends
   * outright. Both are fine for a flourish, where a missed callback costs an
   * animation. A load gate that misses its callback never loads at all, and a
   * tab that was in the background when the reader scrolled past would show
   * them an empty box.
   *
   * So the check is the rect itself, on mount and on scroll, and it unhooks as
   * soon as it fires. No frames involved.
   */
  const [near, setNear] = useState(eager);

  useEffect(() => {
    if (eager) return;
    const host = hostRef.current;
    if (!host) return;
    let done = false;
    const check = () => {
      if (done) return;
      const r = host.getBoundingClientRect();
      // A `display: none` element reports an all-zero rect, and zero is very
      // near the top of the viewport -- so without this the phone downloads
      // every model on the page for slots it will never draw. No box, no
      // fetch; the resize listener picks it up if the slot ever opens.
      if (!r.width && !r.height) return;
      // A screen and a half out, so it is decoded by the time it is looked at.
      if (r.top < window.innerHeight * 1.6) {
        done = true;
        setNear(true);
        window.removeEventListener("scroll", check);
        window.removeEventListener("resize", check);
      }
    };
    check();
    window.addEventListener("scroll", check, { passive: true });
    window.addEventListener("resize", check, { passive: true });

    /**
     * The check that matters most, and the one a scroll listener cannot make.
     *
     * "No box, no fetch" is right for a slot a media query has closed, but it
     * is also true for one measured before first layout -- and a hero model
     * sits in view from the start, so nothing scrolls and nothing resizes and
     * the fetch never happens. Watching the element itself covers both: a
     * closed slot never gains a size, and one that gains a size, whether by
     * layout settling or by a breakpoint opening, is checked the moment it
     * does.
     */
    const ro = new ResizeObserver(check);
    ro.observe(host);

    return () => {
      window.removeEventListener("scroll", check);
      window.removeEventListener("resize", check);
      ro.disconnect();
    };
  }, [eager]);

  useEffect(() => {
    const node = canvasRef.current;
    if (!node || !near) return;

    let disposed = false;
    const cleanup: (() => void)[] = [];

    const start = async () => {
      const gl = node.getContext("webgl", { alpha: true, antialias: true });
      if (!gl) {
        setFailed(true);
        return;
      }

      let buffer: ArrayBuffer;
      try {
        // Default cache mode, deliberately. "force-cache" uses a cached copy
        // even when it is stale, and these files live at stable URLs with no
        // content hash -- so updating a model would keep serving returning
        // visitors the old one indefinitely. The static server sends
        // Last-Modified and ETag; letting the browser revalidate costs one
        // conditional request and cannot go stale.
        const res = await fetch(src);
        if (!res.ok) throw new Error(String(res.status));
        buffer = await res.arrayBuffer();
      } catch {
        setFailed(true);
        return;
      }
      if (disposed) return;

      /* ---- the parser ----------------------------------------------------
         GLB is a 12-byte header then length-prefixed chunks: JSON first, then
         the binary blob every accessor indexes into. */
      let json: GltfDoc;
      let bin: Uint8Array | null = null;
      try {
        const view = new DataView(buffer);
        if (view.getUint32(0, true) !== 0x46546c67) throw new Error("not a glb");
        let off = 12;
        let parsed: GltfDoc | null = null;
        while (off < view.byteLength) {
          const len = view.getUint32(off, true);
          const type = view.getUint32(off + 4, true);
          if (type === 0x4e4f534a) {
            parsed = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, off + 8, len)));
          } else if (type === 0x004e4942) {
            bin = new Uint8Array(buffer, off + 8, len);
          }
          off += 8 + len + ((4 - (len % 4)) % 4);
        }
        if (!parsed || !bin) throw new Error("missing chunk");
        json = parsed;
      } catch {
        setFailed(true);
        return;
      }

      const binary = bin;

      /* ---- buffers, one per bufferView -----------------------------------
         The first version uploaded one buffer per *accessor* and assumed each
         was tightly packed, reasoning that gltf-transform writes a view per
         accessor. It does not, and the file says so plainly: every attribute
         view here carries byteStride 16 -- POSITION and NORMAL interleaved
         into one view -- and all fourteen index accessors share bufferView 0
         at different offsets.

         Reading count * 3 * 2 bytes contiguously out of a 16-byte-strided
         region gets the first vertex right and every one after it wrong. That
         is why the model rendered as a cloud of shrapnel: real triangles,
         drawn between coordinates that were never a suit.

         WebGL reads strided data natively. Upload each view once, whole, and
         let vertexAttribPointer and drawElements do the walking. */
      const viewBuffers = new Map<string, WebGLBuffer>();
      const viewBuffer = (bvIndex: number, target: number) => {
        const key = bvIndex + ":" + target;
        const cached = viewBuffers.get(key);
        if (cached) return cached;
        const bv = json.bufferViews[bvIndex];
        const b = gl.createBuffer();
        if (!b) throw new Error("buffer");
        const bytes = new Uint8Array(
          binary.buffer,
          binary.byteOffset + (bv.byteOffset ?? 0),
          bv.byteLength,
        );
        gl.bindBuffer(target, b);
        gl.bufferData(target, bytes, gl.STATIC_DRAW);
        viewBuffers.set(key, b);
        return b;
      };

      const attr = (index: number): Attr => {
        const acc = json.accessors[index];
        const bv = json.bufferViews[acc.bufferView];
        const [glType] = COMPONENT[acc.componentType];
        return {
          buffer: viewBuffer(acc.bufferView, gl.ARRAY_BUFFER),
          type: glType,
          normalized: !!acc.normalized,
          stride: bv.byteStride ?? 0,
          offset: acc.byteOffset ?? 0,
        };
      };

      const prims: Prim[] = [];
      for (const mesh of json.meshes ?? []) {
        for (const pr of mesh.primitives ?? []) {
          if (pr.attributes?.POSITION === undefined || pr.indices === undefined) continue;
          const pos = attr(pr.attributes.POSITION);
          const nrm = pr.attributes.NORMAL !== undefined ? attr(pr.attributes.NORMAL) : pos;
          const idxAcc = json.accessors[pr.indices];
          const mat = pr.material !== undefined ? json.materials?.[pr.material] : undefined;
          const base = mat?.pbrMetallicRoughness?.baseColorFactor ?? [0.8, 0.8, 0.8, 1];

          prims.push({
            pos,
            nrm,
            indices: viewBuffer(idxAcc.bufferView, gl.ELEMENT_ARRAY_BUFFER),
            indexType: COMPONENT[idxAcc.componentType][0],
            // The indices share a view too, so the draw starts at an offset
            // into it rather than at zero.
            indexOffset: idxAcc.byteOffset ?? 0,
            count: idxAcc.count,
            // The factors are authored sRGB-ish; a mild curve keeps them from
            // reading washed out against a very dark page.
            color: [
              Math.pow(base[0], 1.4),
              Math.pow(base[1], 1.4),
              Math.pow(base[2], 1.4),
            ],
          });
        }
      }
      if (!prims.length) {
        setFailed(true);
        return;
      }

      /* ---- programme ----------------------------------------------------- */
      const compile = (type: number, src: string) => {
        const sh = gl.createShader(type);
        if (!sh) throw new Error("shader");
        gl.shaderSource(sh, src);
        gl.compileShader(sh);
        if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
          throw new Error(gl.getShaderInfoLog(sh) ?? "compile");
        }
        return sh;
      };

      let program: WebGLProgram;
      try {
        const p = gl.createProgram();
        if (!p) throw new Error("program");
        gl.attachShader(p, compile(gl.VERTEX_SHADER, VERT));
        gl.attachShader(p, compile(gl.FRAGMENT_SHADER, FRAG));
        gl.linkProgram(p);
        if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error("link");
        program = p;
      } catch {
        setFailed(true);
        return;
      }

      gl.useProgram(program);
      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.CULL_FACE);

      const aPos = gl.getAttribLocation(program, "aPos");
      const aNrm = gl.getAttribLocation(program, "aNrm");
      const U = {
        proj: gl.getUniformLocation(program, "uProj"),
        view: gl.getUniformLocation(program, "uView"),
        model: gl.getUniformLocation(program, "uModel"),
        normal: gl.getUniformLocation(program, "uNormal"),
        color: gl.getUniformLocation(program, "uColor"),
      };
      gl.enableVertexAttribArray(aPos);
      gl.enableVertexAttribArray(aNrm);

      /* ---- the node's own transform ---------------------------------------
         Quantization pushes a scale and an offset onto the node, so ignoring
         it renders the figure at a few thousandths of its size. */
      const n0 = json.nodes?.[0] ?? {};
      const T = n0.translation ?? [0, 0, 0];
      const R = n0.rotation ?? [0, 0, 0, 1];
      const S = n0.scale ?? [1, 1, 1];

      const [qx, qy, qz, qw] = R;
      const base = [
        (1 - 2 * (qy * qy + qz * qz)) * S[0], 2 * (qx * qy + qz * qw) * S[0], 2 * (qx * qz - qy * qw) * S[0], 0,
        2 * (qx * qy - qz * qw) * S[1], (1 - 2 * (qx * qx + qz * qz)) * S[1], 2 * (qy * qz + qx * qw) * S[1], 0,
        2 * (qx * qz + qy * qw) * S[2], 2 * (qy * qz - qx * qw) * S[2], (1 - 2 * (qx * qx + qy * qy)) * S[2], 0,
        T[0], T[1], T[2], 1,
      ];

      const mul = (a: number[], b: number[]) => {
        const o = new Array<number>(16).fill(0);
        for (let i = 0; i < 4; i++) {
          for (let j = 0; j < 4; j++) {
            for (let k = 0; k < 4; k++) o[i * 4 + j] += a[i * 4 + k] * b[k * 4 + j];
          }
        }
        return o;
      };
      const spinY = (a: number) => {
        const c = Math.cos(a);
        const s = Math.sin(a);
        return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1];
      };

      /* ---- fit it in frame -------------------------------------------------
         Measured rather than guessed: the bounds come from the accessors' own
         min/max, pushed through the node transform, so the framing is right
         whatever the exporter did with the pivot. */
      const lo = [Infinity, Infinity, Infinity];
      const hi = [-Infinity, -Infinity, -Infinity];
      for (const mesh of json.meshes ?? []) {
        for (const pr of mesh.primitives ?? []) {
          const acc = pr.attributes?.POSITION !== undefined ? json.accessors[pr.attributes.POSITION] : null;
          if (!acc?.min || !acc?.max) continue;
          // Into the same space the shader will see them in.
          const div = acc.normalized ? (NORMALIZE_DIV[acc.componentType] ?? 1) : 1;
          const lo3 = acc.min.map((v) => v / div);
          const hi3 = acc.max.map((v) => v / div);
          for (const cx of [lo3[0], hi3[0]]) {
            for (const cy of [lo3[1], hi3[1]]) {
              for (const cz of [lo3[2], hi3[2]]) {
                const v = [
                  base[0] * cx + base[4] * cy + base[8] * cz + base[12],
                  base[1] * cx + base[5] * cy + base[9] * cz + base[13],
                  base[2] * cx + base[6] * cy + base[10] * cz + base[14],
                ];
                for (let i = 0; i < 3; i++) {
                  lo[i] = Math.min(lo[i], v[i]);
                  hi[i] = Math.max(hi[i], v[i]);
                }
              }
            }
          }
        }
      }
      const centre = [0, 1, 2].map((i) => (lo[i] + hi[i]) / 2);
      const span = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) || 1;
      const toOrigin = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -centre[0], -centre[1], -centre[2], 1];

      let W = 0;
      let H = 0;
      const resize = () => {
        const r = node.getBoundingClientRect();
        if (!r.width || !r.height) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = Math.round(r.width * dpr);
        H = Math.round(r.height * dpr);
        node.width = W;
        node.height = H;
        gl.viewport(0, 0, W, H);
      };
      resize();
      const ro = new ResizeObserver(resize);
      ro.observe(node);
      cleanup.push(() => ro.disconnect());

      let spin = -0.35;

      const draw = () => {
        if (!W || !H) return;
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

        const aspect = W / H;
        const f = 1 / Math.tan((30 * Math.PI) / 180 / 2);
        const near = span * 0.05;
        const far = span * 12;
        gl.uniformMatrix4fv(U.proj, false, new Float32Array([
          f / aspect, 0, 0, 0,
          0, f, 0, 0,
          0, 0, (far + near) / (near - far), -1,
          0, 0, (2 * far * near) / (near - far), 0,
        ]));
        // Size scales as 1/dist, so this is measured per model rather than
        // guessed. The suit at 2.25 fills 86% of its canvas height with 22px
        // of margin at the tightest of twelve angles.
        const dist = span * fit;
        gl.uniformMatrix4fv(U.view, false, new Float32Array([
          1, 0, 0, 0,
          0, 1, 0, 0,
          0, 0, 1, 0,
          0, 0, -dist, 1,
        ]));

        // Turn about the figure's own centre, not the file's origin.
        const model = mul(mul(base, toOrigin), spinY(spin));
        gl.uniformMatrix4fv(U.model, false, new Float32Array(model));
        // The rotation block is enough for normals: the scale is uniform.
        gl.uniformMatrix3fv(U.normal, false, new Float32Array([
          model[0], model[1], model[2],
          model[4], model[5], model[6],
          model[8], model[9], model[10],
        ]));

        for (const p of prims) {
          gl.uniform3fv(U.color, p.color);
          gl.bindBuffer(gl.ARRAY_BUFFER, p.pos.buffer);
          gl.vertexAttribPointer(aPos, 3, p.pos.type, p.pos.normalized, p.pos.stride, p.pos.offset);
          gl.bindBuffer(gl.ARRAY_BUFFER, p.nrm.buffer);
          gl.vertexAttribPointer(aNrm, 3, p.nrm.type, p.nrm.normalized, p.nrm.stride, p.nrm.offset);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, p.indices);
          gl.drawElements(gl.TRIANGLES, p.count, p.indexType, p.indexOffset);
        }
      };

      let raf = 0;
      let running = false;
      let last = performance.now();
      const frame = (now: number) => {
        if (!running || disposed) return;
        const dt = Math.min((now - last) / 1000, 0.1);
        last = now;
        if (motionOK) spin += dt * spinRate;
        draw();
        raf = requestAnimationFrame(frame);
      };

      running = true;
      draw();
      raf = requestAnimationFrame(frame);
      cleanup.push(() => {
        running = false;
        cancelAnimationFrame(raf);
      });

      // Stop turning when it is off screen. Unlike the load gate above, an
      // observer that never fires here is harmless: the loop just keeps
      // running, which is what it would have done anyway.
      const vis = new IntersectionObserver(
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
      vis.observe(node);
      cleanup.push(() => vis.disconnect());

      const onLost = (event: Event) => {
        event.preventDefault();
        running = false;
        cancelAnimationFrame(raf);
        setFailed(true);
      };
      node.addEventListener("webglcontextlost", onLost);
      cleanup.push(() => node.removeEventListener("webglcontextlost", onLost));

      // The same synchronous handle every other canvas here exposes, for the
      // same reason: rAF is throttled to a fraction of a hertz in a background
      // tab, so stepping by hand is the only way to assert this moves.
      (window as unknown as Record<string, unknown>)[handleKey] = {
        primitives: prims.length,
        triangles: prims.reduce((sum, p) => sum + p.count / 3, 0),
        span: +span.toFixed(4),
        state: () => ({ spin: +spin.toFixed(3), W, H }),
        tick(seconds: number) {
          spin += seconds * spinRate;
          draw();
          return +spin.toFixed(3);
        },
      };
      cleanup.push(() => {
        delete (window as unknown as Record<string, unknown>)[handleKey];
      });
    };

    void start();

    return () => {
      disposed = true;
      cleanup.forEach((fn) => fn());
    };
  }, [motionOK, near, src, spinRate, fit, handleKey]);

  // A page that reads fine without it should lose nothing when WebGL is
  // unavailable or the model does not arrive.
  if (failed) return null;

  return (
    <div ref={hostRef} className={className}>
      <canvas
        ref={canvasRef}
        className="h-full w-full"
        role="img"
        aria-label={label}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */

/** Only the parts of glTF this file actually reads. */
interface GltfDoc {
  accessors: {
    bufferView: number;
    byteOffset?: number;
    componentType: number;
    count: number;
    type: string;
    normalized?: boolean;
    min?: number[];
    max?: number[];
  }[];
  bufferViews: { byteOffset?: number; byteLength: number; byteStride?: number }[];
  meshes?: {
    primitives?: {
      attributes?: Record<string, number>;
      indices?: number;
      material?: number;
    }[];
  }[];
  materials?: { pbrMetallicRoughness?: { baseColorFactor?: number[] } }[];
  nodes?: { translation?: number[]; rotation?: number[]; scale?: number[] }[];
}


/* -------------------------------------------------------------------------- */

/** The astronaut. Kept as its own name because the page reads better for it. */
export function Suit({ className }: { className?: string }) {
  return (
    <Model
      src="/models/crew-escape-suit.glb"
      label="NASA Advanced Crew Escape Suit, slowly rotating"
      className={className}
      spinRate={0.48}
      fit={2.25}
      handleKey="__havenSuit"
    />
  );
}
