// Transfer mono PCM in batches. Worklet outputs are silent by default.
const batchSamples = 1024;
registerProcessor("lixity-pcm-capture", class extends AudioWorkletProcessor {
  constructor() {
    super();
    this.samples = new Float32Array(batchSamples);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    let offset = 0;
    while (offset < channel.length) {
      const count = Math.min(this.samples.length - this.filled, channel.length - offset);
      this.samples.set(channel.subarray(offset, offset + count), this.filled);
      offset += count;
      this.filled += count;
      if (this.filled === this.samples.length) {
        this.port.postMessage(this.samples, [this.samples.buffer]);
        this.samples = new Float32Array(batchSamples);
        this.filled = 0;
      }
    }
    return true;
  }
});
