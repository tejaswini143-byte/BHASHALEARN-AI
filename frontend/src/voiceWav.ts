export function wavFromFloatChunks(chunks: Float32Array[], sampleRate: number): Blob {
  const inputCount = chunks.reduce((count, chunk) => count + chunk.length, 0);
  if (!inputCount || sampleRate < 1) throw new Error("No microphone audio was captured. Please try again.");
  const input = new Float32Array(inputCount);
  let inputOffset = 0;
  for (const chunk of chunks) { input.set(chunk, inputOffset); inputOffset += chunk.length; }
  const outputRate = 16000;
  const sampleCount = Math.max(1, Math.floor(inputCount * outputRate / sampleRate));
  if (44 + sampleCount * 2 > 10 * 1024 * 1024) throw new Error("Recording exceeds the 10 MB upload limit. Record a shorter clip.");
  const bytes = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(bytes);
  const writeText = (offset: number, value: string) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  writeText(0, "RIFF"); view.setUint32(4, bytes.byteLength - 8, true); writeText(8, "WAVE");
  writeText(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, outputRate, true); view.setUint32(28, outputRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); writeText(36, "data"); view.setUint32(40, sampleCount * 2, true);
  let offset = 44;
  const sourceSamplesPerOutput = sampleRate / outputRate;
  for (let index = 0; index < sampleCount; index += 1) {
    const start = index * sourceSamplesPerOutput;
    const end = Math.min(input.length, (index + 1) * sourceSamplesPerOutput);
    let weighted = 0;
    let weight = 0;
    for (let sourceIndex = Math.floor(start); sourceIndex < Math.ceil(end); sourceIndex += 1) {
      const overlap = Math.max(0, Math.min(end, sourceIndex + 1) - Math.max(start, sourceIndex));
      weighted += input[Math.min(sourceIndex, input.length - 1)] * overlap;
      weight += overlap;
    }
    const sample = weight ? weighted / weight : 0;
    const clipped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([bytes], { type: "audio/wav" });
}
