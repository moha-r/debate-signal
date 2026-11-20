// Average samples into 16 kHz PCM16, preserving fractional boundaries between render blocks.
class VoiceProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.sourceInterval = sampleRate / 16000;
    this.remaining = this.sourceInterval;
    this.integral = 0;
    this.frame = new Int16Array(1600);
    this.used = 0;
    this.energy = 0;
    this.stopped = false;
    this.port.onmessage = ({ data }) => {
      if (data === 'flush') {
        this.stopped = true;
        if (this.used) this.sendFrame();
        this.port.postMessage({ type: 'flushed' });
      }
    };
  }

  sendFrame() {
    const pcm = this.frame;
    const rms = Math.sqrt(this.energy / this.used);
    this.port.postMessage({ type: 'audio', pcm: pcm.buffer, rms }, [pcm.buffer]);
    this.frame = new Int16Array(1600);
    this.used = 0;
    this.energy = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (this.stopped || !channel) return true;
    for (const sample of channel) {
      let available = 1;
      while (available >= this.remaining - 1e-9) {
        const consumed = this.remaining;
        this.integral += sample * consumed;
        available = Math.max(0, available - consumed);
        const point = Math.min(1, Math.max(-1, this.integral / this.sourceInterval));
        this.frame[this.used++] = Math.round(point * (point < 0 ? 32768 : 32767));
        this.energy += point * point;
        this.remaining = this.sourceInterval;
        this.integral = 0;
        if (this.used === this.frame.length) this.sendFrame();
      }
      this.remaining -= available;
      this.integral += sample * available;
    }
    return true;
  }
}

registerProcessor('debate-voice', VoiceProcessor);
