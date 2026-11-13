const TARGET_SAMPLE_RATE = 16000;
const FILTER_RADIUS = 24;

function sinc(value: number): number {
  if (Math.abs(value) < 1e-8) return 1;
  const angle = Math.PI * value;
  return Math.sin(angle) / angle;
}

/** Resample mono float audio with a windowed-sinc low-pass before decimation. */
export function resampleMono(input: Float32Array, inputRate: number, outputRate = TARGET_SAMPLE_RATE): Float32Array {
  if (!input.length || !Number.isFinite(inputRate) || !Number.isFinite(outputRate) || inputRate <= 0 || outputRate <= 0) {
    throw new Error("Audio samples and valid sample rates are required.");
  }
  const outputCount = Math.max(1, Math.floor(input.length * outputRate / inputRate));
  if (inputRate === outputRate) return input.slice(0, outputCount);

  const output = new Float32Array(outputCount);
  const cutoff = Math.min(1, outputRate / inputRate);
  for (let outIndex = 0; outIndex < outputCount; outIndex += 1) {
    const center = outIndex * inputRate / outputRate;
    const first = Math.max(0, Math.floor(center) - FILTER_RADIUS + 1);
    const last = Math.min(input.length - 1, Math.floor(center) + FILTER_RADIUS);
    let weighted = 0;
    let weightTotal = 0;
    for (let sourceIndex = first; sourceIndex <= last; sourceIndex += 1) {
      const distance = center - sourceIndex;
      const windowPosition = distance / FILTER_RADIUS;
      if (Math.abs(windowPosition) >= 1) continue;
      const window = 0.5 + 0.5 * Math.cos(Math.PI * windowPosition);
      const weight = cutoff * sinc(cutoff * distance) * window;
      weighted += input[sourceIndex] * weight;
      weightTotal += weight;
    }
    output[outIndex] = weightTotal ? weighted / weightTotal : 0;
  }
  return output;
}

export function wavFromFloatChunks(chunks: Float32Array[], sampleRate: number): Blob {
  const inputCount = chunks.reduce((count, chunk) => count + chunk.length, 0);
  if (!inputCount || !Number.isFinite(sampleRate) || sampleRate < 1) throw new Error("No microphone audio was captured. Please try again.");
  const input = new Float32Array(inputCount);
  let inputOffset = 0;
  for (const chunk of chunks) { input.set(chunk, inputOffset); inputOffset += chunk.length; }
  const output = resampleMono(input, sampleRate);
  if (44 + output.length * 2 > 10 * 1024 * 1024) throw new Error("Recording exceeds the 10 MB upload limit. Record a shorter clip.");
  const bytes = new ArrayBuffer(44 + output.length * 2);
  const view = new DataView(bytes);
  const writeText = (offset: number, value: string) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  writeText(0, "RIFF"); view.setUint32(4, bytes.byteLength - 8, true); writeText(8, "WAVE");
  writeText(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, TARGET_SAMPLE_RATE, true); view.setUint32(28, TARGET_SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); writeText(36, "data"); view.setUint32(40, output.length * 2, true);
  let offset = 44;
  for (const value of output) {
    const clipped = Math.max(-1, Math.min(1, value));
    view.setInt16(offset, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([bytes], { type: "audio/wav" });
}
