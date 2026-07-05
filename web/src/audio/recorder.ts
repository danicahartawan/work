import { wsUrl } from "../api";
import type { LiveEvent } from "../types";

export interface RecorderOptions {
  meetingId: string;
  captureSystemAudio: boolean; // also grab tab/screen audio via getDisplayMedia
  onEvent: (ev: LiveEvent) => void;
  onError: (message: string) => void;
  onClose: () => void;
}

/**
 * Captures microphone (plus, optionally, system/tab audio), mixes them in a
 * 16 kHz AudioContext, converts to PCM16 in an AudioWorklet, and streams the
 * bytes to the Perch live-transcription WebSocket.
 */
export class LiveRecorder {
  private ctx: AudioContext | null = null;
  private ws: WebSocket | null = null;
  private streams: MediaStream[] = [];
  private stopped = false;

  constructor(private opts: RecorderOptions) {}

  async start(): Promise<void> {
    const mic = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    this.streams.push(mic);

    let system: MediaStream | null = null;
    if (this.opts.captureSystemAudio) {
      // Chrome requires video:true; we only keep the audio track.
      system = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      });
      if (system.getAudioTracks().length === 0) {
        system.getTracks().forEach((t) => t.stop());
        system = null;
        this.opts.onError(
          "No system audio was shared — pick a tab and enable “Share tab audio”. Recording mic only.",
        );
      } else {
        this.streams.push(system);
      }
    }

    this.ws = await this.openSocket();

    // 16 kHz context: the browser resamples all inputs for us.
    this.ctx = new AudioContext({ sampleRate: 16000 });
    await this.ctx.audioWorklet.addModule("/pcm-worklet.js");
    const mixer = this.ctx.createGain();
    for (const stream of this.streams) {
      if (stream.getAudioTracks().length) {
        this.ctx.createMediaStreamSource(stream).connect(mixer);
      }
    }
    const node = new AudioWorkletNode(this.ctx, "pcm16");
    node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
      if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(e.data);
    };
    mixer.connect(node);
    // Keep the graph alive without playing audio back to the user.
    node.connect(this.ctx.createGain()).connect(this.ctx.destination);

    // If the user ends screen sharing from the browser UI, keep going mic-only.
    system?.getVideoTracks()[0]?.addEventListener("ended", () => {
      system?.getTracks().forEach((t) => t.stop());
    });
  }

  private openSocket(): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(wsUrl(this.opts.meetingId));
      ws.binaryType = "arraybuffer";
      ws.onopen = () => resolve(ws);
      ws.onerror = () => reject(new Error("Could not connect to the Perch server."));
      ws.onmessage = (e) => this.opts.onEvent(JSON.parse(e.data) as LiveEvent);
      ws.onclose = () => {
        if (!this.stopped) this.opts.onError("Connection to the server was lost.");
        this.teardownAudio();
        this.opts.onClose();
      };
    });
  }

  /** Stop capturing; the server finishes processing then closes the socket. */
  stop(): void {
    this.stopped = true;
    this.teardownAudio();
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "stop" }));
    } else {
      this.ws?.close();
    }
  }

  private teardownAudio(): void {
    this.streams.forEach((s) => s.getTracks().forEach((t) => t.stop()));
    this.streams = [];
    void this.ctx?.close().catch(() => {});
    this.ctx = null;
  }
}
