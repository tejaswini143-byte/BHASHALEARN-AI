export type VoiceAudioMetrics = {
  durationSeconds: number;
  rmsDbfs: number;
  peakDbfs: number;
  clippedPercent: number;
  speechFramePercent: number;
};

const SPEECH_THRESHOLD = 0.0045; // current voice-onset RMS threshold

export function measureVoiceAudio(chunks: Float32Array[], sampleRate: number): VoiceAudioMetrics {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  if (!sampleCount || !Number.isFinite(sampleRate) || sampleRate <= 0) {
    throw new Error("No microphone audio was captured. Please try again.");
  }
  let sumSquares = 0;
  let peak = 0;
  let clipped = 0;
  let aboveThresholdFrames = 0;
  let frameSquares = 0;
  let frameSamples = 0;
  let samplesSeen = 0;
  const frameLength = Math.max(1, Math.round(sampleRate / 50)); // 20 ms
  for (const chunk of chunks) {
    for (const raw of chunk) {
      const sample = Number.isFinite(raw) ? Math.max(-1, Math.min(1, raw)) : 0;
      const magnitude = Math.abs(sample);
      sumSquares += sample * sample;
      peak = Math.max(peak, magnitude);
      if (magnitude >= 0.999) clipped += 1;
      frameSquares += sample * sample;
      frameSamples += 1;
      samplesSeen += 1;
      if (frameSamples === frameLength || samplesSeen === sampleCount) {
        if (Math.sqrt(frameSquares / frameSamples) >= SPEECH_THRESHOLD) aboveThresholdFrames += 1;
        frameSquares = 0;
        frameSamples = 0;
      }
    }
  }
  const dbfs = (value: number) => value > 0 ? 20 * Math.log10(value) : -120;
  return {
    durationSeconds: sampleCount / sampleRate,
    rmsDbfs: dbfs(Math.sqrt(sumSquares / sampleCount)),
    peakDbfs: dbfs(peak),
    clippedPercent: clipped / sampleCount * 100,
    speechFramePercent: aboveThresholdFrames / Math.ceil(sampleCount / frameLength) * 100,
  };
}
