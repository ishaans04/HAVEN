/**
 * One sun, shared.
 *
 * The hero holds two lit bodies. If each computed its own light direction they
 * would agree only for as long as nobody touched either one, and the moment
 * they drifted the page would be showing a moon whose phase disagreed with the
 * terminator six inches away -- the kind of quiet wrongness a person feels
 * before they can name it, on a page whose whole argument is that things should
 * be checkable.
 *
 * So there is exactly one vector. `Earth` advances it as it steps its own
 * simulation; `Moon` reads it. Deliberately a mutable module object rather than
 * React state: it changes every frame, and routing that through a re-render to
 * move two canvases would cost far more than it buys.
 *
 * Both consumers are canvases painting from the same value in the same frame,
 * so there is no tearing to worry about -- and `phaseAgreesWith` exists so the
 * agreement can be asserted rather than assumed.
 */

export interface SunVector {
  x: number;
  y: number;
  z: number;
}

/** Unit vector towards the sun, in view space. Written by `Earth`. */
export const sun: SunVector = { x: 0.82, y: 0.16, z: 0.55 };

export function setSun(x: number, y: number, z: number) {
  sun.x = x;
  sun.y = y;
  sun.z = z;
}

/**
 * How lit a body at direction `d` would be under the current sun, as a signed
 * cosine. Used by the verification handles on both canvases so that "the moon
 * shows the right phase" is a number rather than an opinion.
 */
export function illuminationOf(d: SunVector) {
  const len = Math.hypot(d.x, d.y, d.z) || 1;
  return (d.x * sun.x + d.y * sun.y + d.z * sun.z) / len;
}
