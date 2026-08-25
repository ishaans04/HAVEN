"use client";

import { useEffect, useRef, useState } from "react";
import { useMotionOK } from "@/lib/motion";
import { illuminationOf, sun } from "@/lib/sun";

/**
 * The moon, in the same light as everything else.
 *
 * A second lit body in the hero, and the reason it is worth having is not that
 * it fills the corner: it is that **its phase is not decided here**. The
 * terminator across it comes from the same sun vector the Earth's terminator
 * comes from, so as that sun swings the crescent narrows and fattens in step
 * with the day/night line on the planet. Two bodies, one light, and the
 * relationship between them is a consequence rather than a decision.
 *
 * That is the difference between this and a moon-shaped png in a corner, and it
 * is the same distinction the rest of the page keeps: the planet's sunrise
 * count is produced by an orbit, the orbit comes from a real element set, the
 * relief comes from a real height field. A crescent drawn to look nice would be
 * the one asserted thing in a hero built entirely of computed ones.
 *
 * Far simpler than `Earth` because a moon is simpler: no atmosphere, no
 * weather, no cities, no oceans to glint. Albedo, a terminator, and the faint
 * blue of earthshine on the dark limb -- which is real, and is sunlight that
 * bounced off the planet next to it.
 */

const VERT = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const FRAG = `
precision highp float;

uniform vec2  uCenter;
uniform float uRadius;
uniform float uSpin;
uniform vec3  uSun;
uniform sampler2D uAlbedo;
uniform float uHasTex;

mat3 rotY(float a) {
  float c = cos(a), s = sin(a);
  return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c);
}

void main() {
  vec2 d = (gl_FragCoord.xy - uCenter) / uRadius;
  float r2 = dot(d, d);
  if (r2 > 1.0) discard;

  float z = sqrt(max(0.0, 1.0 - r2));
  vec3 n = vec3(d, z);
  vec3 p = rotY(-uSpin) * n;

  vec2 uv = vec2(
    0.5 + atan(p.z, p.x) / 6.28318531,
    0.5 - asin(clamp(p.y, -1.0, 1.0)) / 3.14159265
  );

  // Regolith is grey and dark -- about 12% reflective, far darker than a page
  // ever draws it. The fallback keeps that character without the map.
  vec3 albedo = uHasTex > 0.5 ? texture2D(uAlbedo, uv).rgb : vec3(0.44, 0.43, 0.42);

  // The terminator, from the same vector the planet uses. Sharper than Earth's
  // because there is no air to scatter light around the limb.
  float ndl = dot(n, uSun);
  float day = smoothstep(-0.04, 0.10, ndl);

  vec3 lit = albedo * day * 1.06;

  // Earthshine: sunlight off the planet, lighting the part of the moon the sun
  // cannot reach. Blue, because it has been reflected off an ocean.
  lit += albedo * vec3(0.30, 0.42, 0.62) * (1.0 - day) * 0.085;

  // Limb darkening, gentle -- a rocky sphere loses less at the edge than a
  // gassy one, but it does lose some.
  lit *= pow(max(z, 0.0), 0.12);

  float edge = smoothstep(1.0, 1.0 - (1.4 / uRadius), sqrt(r2));
  gl_FragColor = vec4(lit, edge);
}
`;

export function Moon({
  className,
  /**
   * Centre and radius. `cx` and `r` are fractions of the canvas **width**;
   * `cy` is a fraction of its **height**, measured down from the top -- the
   * same convention `Earth.placement` uses, and worth stating because taking
   * `cy` off the width instead put the disc eight pixels from the bottom edge
   * of a 846px buffer and clipped two thirds of it away.
   */
  cx,
  cy,
  r,
}: {
  className?: string;
  cx: number;
  cy: number;
  r: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const motionOK = useMotionOK();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const node = canvasRef.current;
    if (!node) return;

    const gl = node.getContext("webgl", { alpha: true, antialias: false, premultipliedAlpha: false });
    if (!gl) {
      setFailed(true);
      return;
    }

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
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(program, "aPos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    const U = {
      center: gl.getUniformLocation(program, "uCenter"),
      radius: gl.getUniformLocation(program, "uRadius"),
      spin: gl.getUniformLocation(program, "uSpin"),
      sun: gl.getUniformLocation(program, "uSun"),
      albedo: gl.getUniformLocation(program, "uAlbedo"),
      hasTex: gl.getUniformLocation(program, "uHasTex"),
    };

    let ready = false;
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, 1, 1, 0, gl.RGB, gl.UNSIGNED_BYTE,
      new Uint8Array([110, 108, 106]));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.uniform1i(U.albedo, 0);

    let cancelled = false;
    const img = new Image();
    img.onload = () => {
      if (cancelled) return;
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
      ready = true;
      draw();
    };
    // A missing map costs the craters and nothing else: the phase, which is the
    // only thing here carrying meaning, does not depend on it.
    img.onerror = () => {};
    img.src = "/textures/2k_moon.jpg";

    let W = 0;
    let H = 0;
    const resize = () => {
      const rect = node.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = Math.round(rect.width * dpr);
      H = Math.round(rect.height * dpr);
      node.width = W;
      node.height = H;
      gl.viewport(0, 0, W, H);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(node);

    // The moon is tidally locked, so it does not turn relative to us. This is
    // a very slow libration rather than a spin -- the real thing wobbles about
    // eight degrees, which is why we see slightly more than half of it.
    let t = 0;

    const draw = () => {
      if (!W || !H) return;
      gl.uniform2f(U.center, cx * W, H - cy * H);
      gl.uniform1f(U.radius, r * W);
      gl.uniform1f(U.spin, Math.sin(t * 0.04) * 0.14);
      gl.uniform3f(U.sun, sun.x, sun.y, sun.z);
      gl.uniform1f(U.hasTex, ready ? 1 : 0);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };

    let raf = 0;
    let running = true;
    let last = performance.now();
    const frame = (now: number) => {
      if (!running) return;
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      if (motionOK) t += dt;
      draw();
      raf = requestAnimationFrame(frame);
    };
    draw();
    raf = requestAnimationFrame(frame);

    const onLost = (e: Event) => {
      e.preventDefault();
      running = false;
      cancelAnimationFrame(raf);
      setFailed(true);
    };
    node.addEventListener("webglcontextlost", onLost);

    (window as unknown as Record<string, unknown>).__havenMoon = {
      /**
       * The phase, as the cosine between the moon's direction and the sun.
       * Exposed so that "it agrees with the planet" is checkable: this reads
       * the shared vector, and the Earth's handle reports the same one.
       */
      state: () => ({
        sun: { x: +sun.x.toFixed(4), y: +sun.y.toFixed(4), z: +sun.z.toFixed(4) },
        // Straight at the reader is +z, which is where this moon hangs.
        illuminationFacingViewer: +illuminationOf({ x: 0, y: 0, z: 1 }).toFixed(4),
        textured: ready,
        pixels: { W, H, radius: +(r * W).toFixed(1) },
      }),
      tick(seconds: number) {
        t += seconds;
        draw();
        return +t.toFixed(2);
      },
    };

    return () => {
      cancelled = true;
      running = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      node.removeEventListener("webglcontextlost", onLost);
      gl.deleteProgram(program);
      gl.deleteBuffer(buf);
      gl.deleteTexture(tex);
      delete (window as unknown as Record<string, unknown>).__havenMoon;
    };
  }, [cx, cy, r, motionOK]);

  if (failed) return null;
  return <canvas ref={canvasRef} className={className} aria-hidden />;
}
