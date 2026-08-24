/**
 * The real orbit, from a real element set.
 *
 * The hero's planet used to carry three numbers that were close to the ISS
 * without being the ISS: an inclination of 51.64 degrees, a period rounded to
 * 5580 seconds, and an altitude ratio of 1.062 annotated "420 km" that actually
 * works out to 395. Close enough to look right, and asserted rather than
 * produced -- which is the one thing this project does not let its visuals do.
 *
 * So the element set ships verbatim and everything else is derived from it. The
 * inclination the sphere is drawn at, the number of revolutions a day, and the
 * altitude are all read out of these two lines. Nothing here is typed twice.
 *
 * A TLE is a snapshot, not a prediction, and this one is stamped below. The
 * orbit drifts: replace the two lines before a demo and every figure that
 * depends on them moves with it.
 */

/**
 * Celestrak GP element set for ISS (ZARYA), NORAD 25544.
 * <https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle>
 */
export const ISS_TLE = [
  "1 25544U 98067A   26236.43525466  .00008197  00000+0  15348-3 0  9992",
  "2 25544  51.6332 322.3014 0007699  78.6726 281.5127 15.49604681582335",
] as const;

/** Earth's equatorial radius, km. */
const EARTH_RADIUS_KM = 6378.137;
/** Standard gravitational parameter, km^3/s^2. */
const MU = 398600.4418;

function parse() {
  const [l1, l2] = ISS_TLE;

  // Columns are fixed-width by definition; slicing is the whole parser.
  const epochRaw = parseFloat(l1.slice(18, 32));
  const yy = Math.floor(epochRaw / 1000);
  const dayOfYear = epochRaw - yy * 1000;
  // Two-digit years: 57-99 are 1900s, 00-56 are 2000s.
  const year = yy < 57 ? 2000 + yy : 1900 + yy;
  const epoch = new Date(Date.UTC(year, 0, 1) + (dayOfYear - 1) * 86400_000);

  const inclinationDeg = parseFloat(l2.slice(8, 16));
  const raanDeg = parseFloat(l2.slice(17, 25));
  // Eccentricity is stored with the leading decimal point implied.
  const eccentricity = parseFloat("0." + l2.slice(26, 33).trim());
  const argPerigeeDeg = parseFloat(l2.slice(34, 42));
  const meanAnomalyDeg = parseFloat(l2.slice(43, 51));
  const revsPerDay = parseFloat(l2.slice(52, 63));

  // Kepler's third law, the other way round: a period gives a semi-major axis.
  const periodSeconds = 86400 / revsPerDay;
  const n = (2 * Math.PI) / periodSeconds;
  const semiMajorAxisKm = Math.cbrt(MU / (n * n));

  return {
    epoch,
    inclinationDeg,
    inclinationRad: (inclinationDeg * Math.PI) / 180,
    raanDeg,
    eccentricity,
    argPerigeeDeg,
    meanAnomalyDeg,
    revsPerDay,
    periodSeconds,
    periodMinutes: periodSeconds / 60,
    semiMajorAxisKm,
    /** Mean altitude above the equatorial radius, km. */
    altitudeKm: semiMajorAxisKm - EARTH_RADIUS_KM,
    /**
     * Orbit radius as a multiple of Earth's, which is the only form the shader
     * wants: it draws a unit sphere.
     */
    radiusRatio: semiMajorAxisKm / EARTH_RADIUS_KM,
  };
}

export const ISS = parse();

/**
 * Whether treating the orbit as a circle is defensible.
 *
 * At this eccentricity perigee and apogee differ by about ten kilometres on a
 * 6,796 km radius, so the circle the hero draws is wrong by roughly a pixel.
 * Worth stating rather than assuming: if a future element set is genuinely
 * elliptical this stops being true, and the drawing would need to change.
 */
export const CIRCULAR_ERROR_KM = 2 * ISS.eccentricity * ISS.semiMajorAxisKm;
