// sizeGuess.js
// Estimates a "nice" real-world size (in meters) for a dropped screenshot and,
// when we know the surface it landed on, fits it neatly inside that surface.
//
// There is no metric ground truth in a raw screenshot, so we lean on a few
// robust heuristics:
//   1. A sensible default physical size that reads well in a room (poster-ish).
//   2. The image aspect ratio, always preserved.
//   3. If plane detection gave us the extents of the surface it was dropped on,
//      shrink to fit within a margin so it never overflows the wall/table.

// Default longest-edge length in meters for a floating screenshot with no
// surface information. ~0.6 m ≈ a large framed poster: big enough to read,
// small enough to sit on most walls.
const DEFAULT_LONGEST_EDGE_M = 0.6;

// Landscape phone/desktop screenshots tend to be UI captures; portrait tends to
// be phone screens. A slightly smaller default for dense UI captures keeps text
// legible without dominating the wall.
const UI_LONGEST_EDGE_M = 0.5;

// Fraction of the surface we allow the image to occupy when auto-fitting, so
// there is always a visual margin around it.
const SURFACE_FILL = 0.82;

// Clamp so a guess never becomes absurd in a real room.
const MIN_LONGEST_EDGE_M = 0.15;
const MAX_LONGEST_EDGE_M = 2.5;

/**
 * @typedef {{ width: number, height: number }} SizeM  // meters
 */

/**
 * Guess a starting size for an image with no surface context.
 * @param {number} pxW image width in pixels
 * @param {number} pxH image height in pixels
 * @returns {SizeM}
 */
export function guessBaseSize(pxW, pxH) {
  const aspect = pxW / pxH; // width / height

  // Very wide captures (dashboards, ultrawide screenshots) read as "UI"; give
  // them the slightly smaller default so they don't swallow a wall.
  const longest =
    aspect > 1.9 || aspect < 0.52 ? UI_LONGEST_EDGE_M : DEFAULT_LONGEST_EDGE_M;

  if (aspect >= 1) {
    // landscape: width is the longest edge
    return clampSize({ width: longest, height: longest / aspect });
  }
  // portrait: height is the longest edge
  return clampSize({ width: longest * aspect, height: longest });
}

/**
 * Fit a size (preserving aspect) inside a surface's extents with a margin.
 * @param {number} pxW image width in pixels
 * @param {number} pxH image height in pixels
 * @param {number} surfaceW available surface width in meters
 * @param {number} surfaceH available surface height in meters
 * @returns {SizeM}
 */
export function fitToSurface(pxW, pxH, surfaceW, surfaceH) {
  const aspect = pxW / pxH;
  const maxW = surfaceW * SURFACE_FILL;
  const maxH = surfaceH * SURFACE_FILL;

  // Start from the surface width, then clamp height, then re-derive width.
  let width = maxW;
  let height = width / aspect;
  if (height > maxH) {
    height = maxH;
    width = height * aspect;
  }
  return clampSize({ width, height });
}

/**
 * Choose the best guess given whatever context we have.
 * @param {number} pxW
 * @param {number} pxH
 * @param {{ width: number, height: number } | null} [surface] surface extents (m)
 * @returns {SizeM}
 */
export function guessSize(pxW, pxH, surface = null) {
  if (surface && surface.width > 0.05 && surface.height > 0.05) {
    const fitted = fitToSurface(pxW, pxH, surface.width, surface.height);
    // Don't let a fit-to-surface guess balloon past our sane maximum, and don't
    // let it shrink below the base guess for a tiny detected patch — if the
    // detected surface is smaller than the base guess, respect the surface.
    return fitted;
  }
  return guessBaseSize(pxW, pxH);
}

function clampSize({ width, height }) {
  const longest = Math.max(width, height);
  if (longest < MIN_LONGEST_EDGE_M) {
    const s = MIN_LONGEST_EDGE_M / longest;
    return { width: width * s, height: height * s };
  }
  if (longest > MAX_LONGEST_EDGE_M) {
    const s = MAX_LONGEST_EDGE_M / longest;
    return { width: width * s, height: height * s };
  }
  return { width, height };
}

export const _internal = {
  DEFAULT_LONGEST_EDGE_M,
  UI_LONGEST_EDGE_M,
  SURFACE_FILL,
  MIN_LONGEST_EDGE_M,
  MAX_LONGEST_EDGE_M,
};
