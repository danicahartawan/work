const $ = (id) => document.getElementById(id);
let timerHandle = null;

init();

async function init() {
  const { serverUrl = "http://localhost:8000" } = await chrome.storage.sync.get("serverUrl");
  $("server").value = serverUrl;

  // Ask the offscreen document (if any) whether a recording is in progress.
  const state = await chrome.runtime
    .sendMessage({ target: "offscreen", type: "get-state" })
    .catch(() => null);
  if (state?.recording) showLive(state);

  $("start").addEventListener("click", start);
  $("stop").addEventListener("click", stop);
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.target !== "popup") return;
  if (msg.type === "transcript") $("caption").textContent = msg.text;
  if (msg.type === "stopped") showIdle();
});

async function start() {
  hideError();
  const serverUrl = ($("server").value.trim() || "http://localhost:8000").replace(/\/+$/, "");
  await chrome.storage.sync.set({ serverUrl });
  const response = await chrome.runtime.sendMessage({
    target: "background",
    type: "start-capture",
    serverUrl,
    title: $("title").value.trim(),
    withMic: $("mic").checked,
  });
  if (response?.error) return showError(response.error);
  showLive({ startedAt: Date.now(), serverUrl, meetingId: response.meetingId });
}

async function stop() {
  await chrome.runtime.sendMessage({ target: "offscreen", type: "stop" }).catch(() => {});
  showIdle();
}

function showLive(state) {
  $("idle").classList.add("hidden");
  $("live").classList.remove("hidden");
  if (state.lastText) $("caption").textContent = state.lastText;
  $("open-web").href = `${state.serverUrl || $("server").value}`.replace(/\/+$/, "");
  const startedAt = state.startedAt || Date.now();
  clearInterval(timerHandle);
  timerHandle = setInterval(() => {
    const s = Math.floor((Date.now() - startedAt) / 1000);
    $("timer").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 500);
}

function showIdle() {
  clearInterval(timerHandle);
  $("live").classList.add("hidden");
  $("idle").classList.remove("hidden");
}

function showError(text) {
  const el = $("error");
  el.textContent = text;
  el.classList.remove("hidden");
}

function hideError() {
  $("error").classList.add("hidden");
}
