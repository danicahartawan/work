// ui.js
// The 2D interface layered over the AR camera feed via WebXR dom-overlay:
// a drag-and-drop / file-picker tray of screenshots, a status line, and the
// place / resize / delete controls. It knows nothing about Three.js — it just
// emits intent through callbacks the app wires up.

/**
 * @typedef {Object} LoadedImage
 * @property {string} id
 * @property {HTMLImageElement} image   decoded, ready to become a texture
 * @property {number} pxW
 * @property {number} pxH
 * @property {string} name
 */

let idCounter = 0;

export function createUI(root, handlers) {
  root.innerHTML = TEMPLATE;

  const els = {
    status: root.querySelector("#status"),
    tray: root.querySelector("#tray"),
    fileInput: root.querySelector("#file-input"),
    dropZone: root.querySelector("#drop-zone"),
    startBtn: root.querySelector("#start-ar"),
    placeBtn: root.querySelector("#place-btn"),
    deleteBtn: root.querySelector("#delete-btn"),
    biggerBtn: root.querySelector("#bigger-btn"),
    smallerBtn: root.querySelector("#smaller-btn"),
    controls: root.querySelector("#controls"),
    hint: root.querySelector("#hint"),
  };

  let selectedId = null;

  // --- file loading -------------------------------------------------------
  async function ingestFiles(fileList) {
    const files = Array.from(fileList).filter((f) =>
      f.type.startsWith("image/"),
    );
    for (const file of files) {
      try {
        const loaded = await loadImageFile(file);
        addThumb(loaded);
        handlers.onImageLoaded?.(loaded);
      } catch (err) {
        console.error("Failed to load image", file.name, err);
      }
    }
    if (files.length)
      setStatus(
        `${files.length} screenshot(s) ready — tap one, then tap the ring to place.`,
      );
  }

  function addThumb(loaded) {
    const btn = document.createElement("button");
    btn.className = "thumb";
    btn.dataset.id = loaded.id;
    btn.title = loaded.name;
    const img = document.createElement("img");
    img.src = loaded.image.src;
    btn.appendChild(img);
    btn.addEventListener("click", () => selectImage(loaded.id));
    els.tray.appendChild(btn);
    selectImage(loaded.id); // auto-select the newest
  }

  function selectImage(id) {
    selectedId = id;
    els.tray.querySelectorAll(".thumb").forEach((t) => {
      t.classList.toggle("selected", t.dataset.id === id);
    });
    handlers.onSelect?.(id);
  }

  // --- drag & drop --------------------------------------------------------
  ["dragenter", "dragover"].forEach((ev) =>
    els.dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      els.dropZone.classList.add("hot");
    }),
  );
  ["dragleave", "drop"].forEach((ev) =>
    els.dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      els.dropZone.classList.remove("hot");
    }),
  );
  els.dropZone.addEventListener("drop", (e) => {
    if (e.dataTransfer?.files?.length) ingestFiles(e.dataTransfer.files);
  });
  els.dropZone.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", (e) => ingestFiles(e.target.files));

  // Whole-window drop so you can drag a screenshot anywhere.
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer?.files?.length) ingestFiles(e.dataTransfer.files);
  });

  // --- buttons ------------------------------------------------------------
  els.startBtn.addEventListener("click", () => handlers.onStartAR?.());
  els.placeBtn.addEventListener("click", () => handlers.onPlace?.());
  els.deleteBtn.addEventListener("click", () => handlers.onDelete?.());
  els.biggerBtn.addEventListener("click", () => handlers.onResize?.(1.12));
  els.smallerBtn.addEventListener("click", () => handlers.onResize?.(1 / 1.12));

  // --- public surface -----------------------------------------------------
  function setStatus(text) {
    els.status.textContent = text;
  }
  function setARMode(on) {
    root.classList.toggle("ar-active", on);
  }
  function setReticleVisible(v) {
    els.placeBtn.disabled = !v;
    els.hint.classList.toggle("ready", v);
  }
  function setHasSelection(v) {
    els.deleteBtn.disabled = !v;
    els.biggerBtn.disabled = !v;
    els.smallerBtn.disabled = !v;
  }
  function showStartButton(supported) {
    els.startBtn.disabled = !supported;
    els.startBtn.textContent = supported
      ? "Enter AR"
      : "AR not supported on this device";
  }
  function getSelectedId() {
    return selectedId;
  }

  return {
    setStatus,
    setARMode,
    setReticleVisible,
    setHasSelection,
    showStartButton,
    getSelectedId,
    ingestFiles,
  };
}

function loadImageFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const image = new Image();
      image.onload = () =>
        resolve({
          id: `img-${++idCounter}`,
          image,
          pxW: image.naturalWidth,
          pxH: image.naturalHeight,
          name: file.name,
        });
      image.onerror = reject;
      image.src = reader.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const TEMPLATE = `
  <div id="panel">
    <h1>AR Room Placer</h1>
    <p id="status">Add screenshots, then enter AR and tap a wall or table to hang them.</p>
    <div id="drop-zone">
      <span>Drag screenshots here, or tap to choose</span>
      <input id="file-input" type="file" accept="image/*" multiple hidden />
    </div>
    <div id="tray"></div>
    <button id="start-ar" class="primary" disabled>Checking AR support…</button>
  </div>

  <div id="hint"><span class="ring-dot"></span>Move your phone to find a surface</div>

  <div id="controls">
    <button id="smaller-btn" disabled title="Smaller">–</button>
    <button id="place-btn" class="primary" disabled>Place here</button>
    <button id="bigger-btn" disabled title="Bigger">+</button>
    <button id="delete-btn" disabled title="Remove selected">🗑</button>
  </div>
`;
