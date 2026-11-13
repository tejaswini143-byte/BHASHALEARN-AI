import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const { measureVoiceAudio } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/voiceAudioMetrics.ts"));

test("microphone metrics report duration, level, frame activity and clipping", () => {
  const samples = new Float32Array(16000).fill(0.01);
  samples[0] = 1;
  const metrics = measureVoiceAudio([samples], 16000);
  assert.equal(metrics.durationSeconds, 1);
  assert.ok(metrics.rmsDbfs < -37 && metrics.rmsDbfs > -39);
  assert.equal(metrics.peakDbfs, 0);
  assert.equal(metrics.clippedPercent, 100 / samples.length);
  assert.equal(metrics.speechFramePercent, 100);
});

test("silent capture reports a low level and zero speech frames", () => {
  const metrics = measureVoiceAudio([new Float32Array(4800)], 48000);
  assert.equal(metrics.durationSeconds, 0.1);
  assert.equal(metrics.rmsDbfs, -120);
  assert.equal(metrics.peakDbfs, -120);
  assert.equal(metrics.speechFramePercent, 0);
});

test("empty capture is rejected before upload", () => {
  assert.throws(() => measureVoiceAudio([], 48000), /No microphone audio was captured/);
});
