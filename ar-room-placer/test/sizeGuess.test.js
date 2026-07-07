// Minimal assertions for the size-guessing logic — the one piece of the app
// that runs without a device or a GPU. Run with: npm test
import assert from "node:assert/strict";
import {
  guessBaseSize,
  fitToSurface,
  guessSize,
  _internal,
} from "../src/sizeGuess.js";

let passed = 0;
function test(name, fn) {
  fn();
  passed++;
  console.log("  ✓ " + name);
}

console.log("sizeGuess");

test("landscape screenshot: width is the longest edge, aspect preserved", () => {
  const s = guessBaseSize(1920, 1080);
  assert.ok(s.width > s.height, "width should exceed height");
  assert.ok(
    Math.abs(s.width / s.height - 1920 / 1080) < 1e-6,
    "aspect preserved",
  );
  assert.ok(s.width <= _internal.MAX_LONGEST_EDGE_M);
});

test("portrait screenshot: height is the longest edge, aspect preserved", () => {
  const s = guessBaseSize(1080, 2340);
  assert.ok(s.height > s.width, "height should exceed width");
  assert.ok(
    Math.abs(s.height / s.width - 2340 / 1080) < 1e-6,
    "aspect preserved",
  );
});

test("ultrawide capture uses the smaller UI default", () => {
  const wide = guessBaseSize(3440, 1000); // aspect ~3.44 -> UI default
  assert.equal(
    Math.max(wide.width, wide.height).toFixed(3),
    _internal.UI_LONGEST_EDGE_M.toFixed(3),
  );
});

test("fitToSurface never exceeds the surface fill margin", () => {
  const s = fitToSurface(1000, 1000, 0.5, 0.5); // square image on 0.5m surface
  assert.ok(s.width <= 0.5 * _internal.SURFACE_FILL + 1e-9);
  assert.ok(s.height <= 0.5 * _internal.SURFACE_FILL + 1e-9);
});

test("fitToSurface preserves aspect while fitting a tall image on a wide surface", () => {
  const s = fitToSurface(500, 1000, 2.0, 0.6); // tall image, wide short surface
  assert.ok(
    Math.abs(s.width / s.height - 500 / 1000) < 1e-6,
    "aspect preserved",
  );
  assert.ok(s.height <= 0.6 * _internal.SURFACE_FILL + 1e-9, "height fits");
});

test("guessSize uses the surface when given, base guess otherwise", () => {
  const withSurface = guessSize(1000, 1000, { width: 0.4, height: 0.4 });
  const without = guessSize(1000, 1000, null);
  assert.ok(withSurface.width <= 0.4 * _internal.SURFACE_FILL + 1e-9);
  assert.ok(without.width > 0, "base guess returns a positive size");
  assert.notEqual(withSurface.width.toFixed(3), without.width.toFixed(3));
});

test("tiny surfaces are ignored (fall back to base guess)", () => {
  const s = guessSize(1000, 1000, { width: 0.01, height: 0.01 });
  const base = guessBaseSize(1000, 1000);
  assert.equal(s.width.toFixed(3), base.width.toFixed(3));
});

console.log(`\n${passed} passed`);
