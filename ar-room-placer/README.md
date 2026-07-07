# AR Room Placer

Point your phone at a room, drag in a screenshot, and it hangs on the wall (or
lays on the table) at a **guessed real-world size** — auto-fit to the surface it
lands on.

It's a small, build-free web app: **WebXR** for the room camera + surface
tracking, **Three.js** for rendering. No app store, no native build.

![flow](https://img.shields.io/badge/WebXR-immersive--ar-33ddff) ![three](https://img.shields.io/badge/three.js-0.160-black)

## How it works

| Step | Tech |
| --- | --- |
| See the room | `immersive-ar` session with camera passthrough (`alpha` canvas) |
| Find the drop spot | **hit-testing** — a reticle rides the surface under the crosshair |
| Orient the image | basis built from the hit **surface normal** → flat on walls, upright text |
| Guess the size | `sizeGuess.js` heuristics from aspect ratio + a room-scale default |
| Fit it nicely | **plane detection** extents shrink the image to ~82% of the surface |
| Keep it there | the mesh is anchored in the `local` reference space |

### Size guessing

A raw screenshot has no metric ground truth, so `src/sizeGuess.js`:

1. Preserves the image aspect ratio, always.
2. Picks a room-scale default (~0.6 m longest edge, a bit smaller for ultrawide
   UI captures).
3. If the runtime reports the **detected plane** the image landed on, fits the
   image inside that plane's extents with a margin so it never overflows the
   wall or table.
4. Clamps to a sane 0.15 m–2.5 m range.

`+` / `–` let you fine-tune after dropping; `🗑` removes.

## Run it

WebXR AR requires **HTTPS** (or `localhost`) and an **AR-capable device** —
Chrome on an ARCore Android phone, or an AR headset browser. iOS Safari does not
support WebXR AR.

```bash
# from this folder
npm start                 # serves http://localhost:8080
```

To test on a phone you need HTTPS. Easiest options:

- **ngrok**: `ngrok http 8080` → open the https URL on your phone.
- **Local certs**: `npm run serve:https` (expects `cert.pem` / `key.pem`).
- Deploy the folder to any static host (GitHub Pages, Netlify, Vercel) — it's
  just static files.

Then: **Enter AR → pan to find a surface → tap a screenshot in the tray → “Place
here”** (or just tap the screen).

On a desktop browser the AR button is disabled, but you can still load
screenshots to see the tray — handy for iterating on the UI.

## Test

```bash
npm test        # runs the size-guessing assertions in Node
```

## Files

```
ar-room-placer/
├── index.html          # shell + import map (Three.js vendored locally)
├── styles.css          # setup panel + in-AR chrome
├── src/
│   ├── app.js          # WebXR session, hit-test reticle, placement, editing
│   ├── ui.js           # drag-drop tray, controls (no Three.js)
│   └── sizeGuess.js    # pure size-estimation heuristics
├── vendor/
│   └── three.module.js # pinned Three.js r160 (no CDN, offline-ready)
└── test/
    └── sizeGuess.test.js
```

## Notes & limits

- **Plane detection** and **anchors** are requested as *optional* features. Where
  the runtime lacks them, placement still works — it falls back to the default
  size guess and a `local`-space transform.
- Anchoring uses the `local` reference space; over long sessions objects may
  drift slightly as tracking refines. Swapping in WebXR **anchors** (already an
  optional feature) is the upgrade path for rock-solid persistence.
- Three.js is vendored at `vendor/three.module.js` and wired through an import
  map, so this is a zero-build, copy-and-serve, fully-offline app — no CDN.
  To upgrade: drop in a newer `three.module.js` (r160+ for the WebXR APIs used).
