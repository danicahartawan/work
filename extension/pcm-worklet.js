// AudioWorklet: convert float32 frames to 16-bit PCM and batch them into
// ~128 ms messages so the WebSocket isn't flooded with tiny frames.
class PCM16Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Int16Array(2048);
    this.len = 0;
  }
  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (input) {
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        this.buf[this.len++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this.len === this.buf.length) {
          this.port.postMessage(this.buf.slice(0, this.len).buffer, []);
          this.len = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("pcm16", PCM16Processor);
