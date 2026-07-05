// Service worker: owns tab-capture stream IDs and the offscreen document.
// The offscreen document does the actual audio work (getUserMedia is not
// available in MV3 service workers).

const OFFSCREEN_URL = "offscreen.html";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.target !== "background") return;
  if (msg.type === "start-capture") {
    startCapture(msg).then(sendResponse).catch((e) => sendResponse({ error: String(e.message || e) }));
    return true; // async response
  }
  if (msg.type === "recording-state") {
    chrome.action.setBadgeText({ text: msg.recording ? "REC" : "" });
    if (msg.recording) chrome.action.setBadgeBackgroundColor({ color: "#e0443a" });
  }
});

async function startCapture({ serverUrl, title, withMic }) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) throw new Error("No active tab.");
  if (/^(chrome|edge|about|chrome-extension):/.test(tab.url || "")) {
    throw new Error("This page can't be captured — open your meeting tab first.");
  }

  const streamId = await chrome.tabCapture.getMediaStreamId({
    targetTabId: tab.id,
  });

  await ensureOffscreen();
  const response = await chrome.runtime.sendMessage({
    target: "offscreen",
    type: "start",
    streamId,
    serverUrl,
    withMic,
    title: title || tab.title || "Meeting",
  });
  if (response?.error) throw new Error(response.error);
  return response;
}

async function ensureOffscreen() {
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
  });
  if (contexts.length === 0) {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      reasons: ["USER_MEDIA"],
      justification: "Capture tab and microphone audio for live transcription",
    });
  }
}
