// Offscreen document: mixes tab audio + microphone at 16 kHz, converts to
// PCM16 in an AudioWorklet, and streams it to the Perch server. Also keeps
// playing the tab audio locally so capturing doesn't mute the meeting.

let session = null; // { ws, ctx, streams, meetingId, serverUrl, title, startedAt, lastText }

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.target !== "offscreen") return;
  if (msg.type === "start") {
    start(msg).then(sendResponse).catch((e) => {
      sendResponse({ error: String(e.message || e) });
    });
    return true;
  }
  if (msg.type === "stop") {
    stop();
    sendResponse({ ok: true });
  }
  if (msg.type === "get-state") {
    sendResponse(stateSnapshot());
  }
});

function stateSnapshot() {
  if (!session) return { recording: false };
  return {
    recording: true,
    meetingId: session.meetingId,
    title: session.title,
    serverUrl: session.serverUrl,
    startedAt: session.startedAt,
    lastText: session.lastText || "",
  };
}

async function start({ streamId, serverUrl, withMic, title }) {
  if (session) throw new Error("Already recording.");
  serverUrl = (serverUrl || "http://localhost:8000").replace(/\/+$/, "");

  // 1. Create the meeting on the server.
  const res = await fetch(`${serverUrl}/api/meetings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`Server error: ${res.status}`);
  const meeting = await res.json();

  // 2. Capture tab audio (and mic, if allowed).
  const streams = [];
  const tabStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId },
    },
  });
  streams.push(tabStream);
  if (withMic) {
    try {
      streams.push(
        await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
        }),
      );
    } catch {
      // No mic permission for the extension — proceed with tab audio only.
    }
  }

  // 3. Open the live-transcription socket.
  const ws = await openSocket(
    `${serverUrl.replace(/^http/, "ws")}/ws/meetings/${meeting.id}/audio`,
  );

  // 4. Build the 16 kHz capture graph.
  const ctx = new AudioContext({ sampleRate: 16000 });
  await ctx.audioWorklet.addModule("pcm-worklet.js");
  const mixer = ctx.createGain();
  for (const s of streams) ctx.createMediaStreamSource(s).connect(mixer);
  const node = new AudioWorkletNode(ctx, "pcm16");
  node.port.onmessage = (e) => {
    if (ws.readyState === WebSocket.OPEN) ws.send(e.data);
  };
  mixer.connect(node);
  // Route ONLY the tab stream back to the speakers (never the mic).
  ctx.createMediaStreamSource(tabStream).connect(ctx.destination);

  session = {
    ws,
    ctx,
    streams,
    meetingId: meeting.id,
    serverUrl,
    title,
    startedAt: Date.now(),
    lastText: "",
  };
  chrome.runtime.sendMessage({ target: "background", type: "recording-state", recording: true });
  return { ok: true, meetingId: meeting.id };
}

function openSocket(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => resolve(ws);
    ws.onerror = () => reject(new Error("Could not connect to the Perch server."));
    ws.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if ((ev.type === "partial" || ev.type === "final") && session) {
        session.lastText = ev.segment.text;
        chrome.runtime
          .sendMessage({ target: "popup", type: "transcript", text: ev.segment.text })
          .catch(() => {});
      }
      if (ev.type === "status" && ev.status === "done") teardown();
    };
    ws.onclose = () => teardown();
  });
}

function stop() {
  if (!session) return;
  const { ws, ctx, streams } = session;
  streams.forEach((s) => s.getTracks().forEach((t) => t.stop()));
  ctx.close().catch(() => {});
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "stop" })); // server closes after processing
  } else {
    teardown();
  }
}

function teardown() {
  if (!session) return;
  session.streams.forEach((s) => s.getTracks().forEach((t) => t.stop()));
  session.ctx.close().catch(() => {});
  session = null;
  chrome.runtime.sendMessage({ target: "background", type: "recording-state", recording: false });
  chrome.runtime.sendMessage({ target: "popup", type: "stopped" }).catch(() => {});
}
