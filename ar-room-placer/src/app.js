// app.js
// Ties the room camera (WebXR immersive-ar) to the drop tray: a reticle rides
// the surface under the crosshair using hit-testing, and when you place a
// selected screenshot it is oriented flat to that surface, sized by guessSize()
// (fitting the detected plane when we have one), and left anchored in the room.

import * as THREE from "three";
import { createUI } from "./ui.js";
import { guessSize } from "./sizeGuess.js";

const overlay = document.getElementById("overlay");
const canvas = document.getElementById("gl");

let renderer, scene, camera;
let reticle;
const textures = new Map(); // imageId -> { texture, pxW, pxH }
const placed = []; // { mesh, imageId }
let selectedPlaced = null; // the placed mesh currently targeted by resize/delete

// XR state
let xrSession = null;
let xrRefSpace = null;
let viewerSpace = null;
let hitTestSource = null;
let reticleValid = false;
let latestFrame = null; // most recent XRFrame, used for plane-detection lookups
const reticlePose = {
  position: new THREE.Vector3(),
  normal: new THREE.Vector3(0, 1, 0),
};

const ui = createUI(overlay, {
  onImageLoaded: registerImage,
  onStartAR: startAR,
  onPlace: placeSelected,
  onDelete: deleteSelected,
  onResize: resizeSelected,
});

initThree();
checkSupport();

// ---------------------------------------------------------------------------
// Three.js scaffolding
// ---------------------------------------------------------------------------
function initThree() {
  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: false,
  });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.xr.enabled = true;

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(
    70,
    window.innerWidth / window.innerHeight,
    0.01,
    40,
  );

  scene.add(new THREE.HemisphereLight(0xffffff, 0x666677, 1.1));
  const dir = new THREE.DirectionalLight(0xffffff, 0.6);
  dir.position.set(0.5, 1, 0.25);
  scene.add(dir);

  reticle = makeReticle();
  reticle.visible = false;
  scene.add(reticle);

  window.addEventListener("resize", onResize);
}

function makeReticle() {
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.07, 0.09, 40),
    new THREE.MeshBasicMaterial({
      color: 0x33ddff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.95,
    }),
  );
  const dot = new THREE.Mesh(
    new THREE.CircleGeometry(0.012, 24),
    new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide }),
  );
  const g = new THREE.Group();
  g.add(ring, dot);
  g.matrixAutoUpdate = false;
  return g;
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// ---------------------------------------------------------------------------
// Image registration -> GPU texture
// ---------------------------------------------------------------------------
function registerImage(loaded) {
  const texture = new THREE.Texture(loaded.image);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  textures.set(loaded.id, { texture, pxW: loaded.pxW, pxH: loaded.pxH });
}

// ---------------------------------------------------------------------------
// AR support + session lifecycle
// ---------------------------------------------------------------------------
async function checkSupport() {
  const supported =
    "xr" in navigator &&
    (await navigator.xr
      .isSessionSupported?.("immersive-ar")
      .catch(() => false));
  ui.showStartButton(!!supported);
  if (!supported) {
    ui.setStatus(
      "This browser can’t run WebXR AR. Use Chrome on an ARCore Android phone (or an AR-capable headset) over HTTPS. You can still load screenshots to preview the tray.",
    );
  }
}

async function startAR() {
  if (xrSession) return;
  try {
    xrSession = await navigator.xr.requestSession("immersive-ar", {
      requiredFeatures: ["hit-test", "local"],
      optionalFeatures: ["dom-overlay", "plane-detection", "anchors"],
      domOverlay: { root: overlay },
    });
  } catch (err) {
    ui.setStatus("Could not start AR: " + err.message);
    return;
  }

  ui.setARMode(true);
  ui.setStatus("Move your phone slowly to scan the room…");

  renderer.xr.setReferenceSpaceType("local");
  await renderer.xr.setSession(xrSession);

  xrRefSpace = await xrSession.requestReferenceSpace("local");
  viewerSpace = await xrSession.requestReferenceSpace("viewer");
  hitTestSource = await xrSession.requestHitTestSource({ space: viewerSpace });

  // Tapping the screen also places (in addition to the Place button).
  xrSession.addEventListener("select", onXRSelect);
  xrSession.addEventListener("end", onSessionEnd);

  renderer.setAnimationLoop(onXRFrame);
}

function onSessionEnd() {
  hitTestSource?.cancel?.();
  hitTestSource = null;
  xrSession = null;
  reticle.visible = false;
  reticleValid = false;
  ui.setARMode(false);
  ui.setReticleVisible(false);
  renderer.setAnimationLoop(null);
  ui.setStatus("AR session ended. Enter AR to place more screenshots.");
}

// ---------------------------------------------------------------------------
// Per-frame: update reticle from hit-test
// ---------------------------------------------------------------------------
function onXRFrame(_time, frame) {
  if (!frame) return;

  const results = hitTestSource ? frame.getHitTestResults(hitTestSource) : [];
  if (results.length) {
    const pose = results[0].getPose(xrRefSpace);
    if (pose) {
      const m = new THREE.Matrix4().fromArray(pose.transform.matrix);
      reticlePose.position.setFromMatrixPosition(m);
      // WebXR hit-test poses expose the surface normal as the +Y basis vector.
      reticlePose.normal.setFromMatrixColumn(m, 1).normalize();

      const camPos = new THREE.Vector3().setFromMatrixPosition(
        camera.matrixWorld,
      );
      const basis = orientToSurface(
        reticlePose.position,
        reticlePose.normal,
        camPos,
      );
      reticle.matrix.copy(basis);
      if (!reticleValid) {
        reticleValid = true;
        reticle.visible = true;
        ui.setReticleVisible(true);
        ui.setStatus("Surface found. Tap a screenshot, then tap “Place here”.");
      }
    }
  } else if (reticleValid) {
    reticleValid = false;
    reticle.visible = false;
    ui.setReticleVisible(false);
    ui.setStatus("Lost the surface — pan your phone to find a wall or table.");
  }

  // Keep detected-plane extents fresh for the next placement.
  latestFrame = frame;

  renderer.render(scene, camera);
}

// ---------------------------------------------------------------------------
// Orientation: build a basis that lies flat on the surface, image upright.
// Columns: X = right, Y = up, Z = forward(=surface normal). A plane facing +Z
// therefore faces out of the surface, spanning right/up.
// ---------------------------------------------------------------------------
function orientToSurface(position, normal, cameraPos) {
  const worldUp = new THREE.Vector3(0, 1, 0);
  const forward = normal.clone().normalize();
  let right, up;

  if (Math.abs(forward.dot(worldUp)) > 0.95) {
    // Near-horizontal surface (floor/ceiling/table): pick a yaw that faces the
    // viewer so the image's "up" points back toward you.
    const toCam = cameraPos.clone().sub(position);
    toCam.y = 0;
    if (toCam.lengthSq() < 1e-6) toCam.set(0, 0, 1);
    toCam.normalize();
    up = toCam;
    right = new THREE.Vector3().crossVectors(up, forward).normalize();
    up = new THREE.Vector3().crossVectors(forward, right).normalize();
  } else {
    // Vertical-ish surface (wall): keep the image's up as close to world-up as
    // possible so text isn't tilted.
    right = new THREE.Vector3().crossVectors(worldUp, forward).normalize();
    up = new THREE.Vector3().crossVectors(forward, right).normalize();
  }
  return new THREE.Matrix4()
    .makeBasis(right, up, forward)
    .setPosition(position);
}

// ---------------------------------------------------------------------------
// Placement
// ---------------------------------------------------------------------------
function onXRSelect() {
  placeSelected();
}

function placeSelected() {
  if (!reticleValid) return;
  const id = ui.getSelectedId();
  const entry = id && textures.get(id);
  if (!entry) {
    ui.setStatus("Pick a screenshot from the tray first.");
    return;
  }

  const surface = estimateSurfaceExtents(
    reticlePose.position,
    reticlePose.normal,
  );
  const size = guessSize(entry.pxW, entry.pxH, surface);

  const mesh = makeImageMesh(entry.texture, size);
  const camPos = new THREE.Vector3().setFromMatrixPosition(camera.matrixWorld);
  const basis = orientToSurface(
    reticlePose.position,
    reticlePose.normal,
    camPos,
  );
  // Nudge a few mm off the surface to avoid z-fighting with the real wall.
  const lift = reticlePose.normal.clone().multiplyScalar(0.005);
  basis.setPosition(reticlePose.position.clone().add(lift));

  mesh.matrixAutoUpdate = false;
  mesh.matrix.copy(basis);
  scene.add(mesh);

  const record = { mesh, imageId: id, baseSize: size };
  placed.push(record);
  selectedPlaced = record;
  ui.setHasSelection(true);

  const cm = (v) => Math.round(v * 100);
  ui.setStatus(
    `Placed at ~${cm(size.width)}×${cm(size.height)} cm` +
      (surface ? " (fit to the surface)." : " (estimated).") +
      " Use + / – to fine-tune, 🗑 to remove.",
  );
}

function makeImageMesh(texture, size) {
  const geo = new THREE.PlaneGeometry(size.width, size.height);
  const mat = new THREE.MeshBasicMaterial({
    map: texture,
    side: THREE.DoubleSide,
    transparent: true,
  });
  const mesh = new THREE.Mesh(geo, mat);

  // A thin frame so the screenshot reads as a hung print, not a floating decal.
  const frame = new THREE.Mesh(
    new THREE.PlaneGeometry(
      size.width * 1.05 + 0.01,
      size.height * 1.05 + 0.01,
    ),
    new THREE.MeshBasicMaterial({ color: 0x111318, side: THREE.DoubleSide }),
  );
  frame.position.z = -0.001;
  mesh.add(frame);
  return mesh;
}

// ---------------------------------------------------------------------------
// Plane detection: if the runtime exposes detected planes, find the one this
// hit landed on and return its extents (meters) so guessSize can fit to it.
// Best-effort — returns null when plane detection isn't available.
// ---------------------------------------------------------------------------
function estimateSurfaceExtents(hitPos, hitNormal) {
  const frame = latestFrame;
  if (!frame || !frame.detectedPlanes || !xrRefSpace) return null;

  let best = null;
  let bestDist = Infinity;

  for (const plane of frame.detectedPlanes) {
    const pose = frame.getPose(plane.planeSpace, xrRefSpace);
    if (!pose) continue;
    const m = new THREE.Matrix4().fromArray(pose.transform.matrix);
    const planePos = new THREE.Vector3().setFromMatrixPosition(m);
    const planeNormal = new THREE.Vector3()
      .setFromMatrixColumn(m, 1)
      .normalize();

    // Skip planes whose orientation disagrees with the hit surface.
    if (planeNormal.dot(hitNormal) < 0.7) continue;

    const d = planePos.distanceTo(hitPos);
    if (d < bestDist) {
      bestDist = d;
      best = plane;
    }
  }

  if (!best || bestDist > 1.5) return null;

  // Polygon points are in the plane's local X/Z. Their span gives the extents.
  const poly = best.polygon;
  if (!poly || poly.length < 3) return null;
  let minX = Infinity,
    maxX = -Infinity,
    minZ = Infinity,
    maxZ = -Infinity;
  for (const p of poly) {
    minX = Math.min(minX, p.x);
    maxX = Math.max(maxX, p.x);
    minZ = Math.min(minZ, p.z);
    maxZ = Math.max(maxZ, p.z);
  }
  const width = maxX - minX;
  const height = maxZ - minZ;
  if (!(width > 0.05) || !(height > 0.05)) return null;
  return { width, height };
}

// ---------------------------------------------------------------------------
// Editing the most recently placed image
// ---------------------------------------------------------------------------
function resizeSelected(factor) {
  if (!selectedPlaced) return;
  // Scale the plane in its own local X/Y (right/up) without touching position:
  // matrix * scale leaves the translation column untouched.
  const scaleM = new THREE.Matrix4().makeScale(factor, factor, 1);
  selectedPlaced.mesh.matrix.multiply(scaleM);
  selectedPlaced.mesh.matrixWorldNeedsUpdate = true;
}

function deleteSelected() {
  if (!selectedPlaced) return;
  scene.remove(selectedPlaced.mesh);
  disposeMesh(selectedPlaced.mesh);
  const idx = placed.indexOf(selectedPlaced);
  if (idx >= 0) placed.splice(idx, 1);
  selectedPlaced = placed[placed.length - 1] || null;
  ui.setHasSelection(!!selectedPlaced);
  ui.setStatus(
    selectedPlaced ? "Removed. Editing the previous image." : "Removed.",
  );
}

function disposeMesh(mesh) {
  mesh.geometry?.dispose();
  if (mesh.material) {
    // keep shared texture alive; just drop the material
    mesh.material.dispose?.();
  }
  mesh.children.forEach((c) => {
    c.geometry?.dispose();
    c.material?.dispose?.();
  });
}
