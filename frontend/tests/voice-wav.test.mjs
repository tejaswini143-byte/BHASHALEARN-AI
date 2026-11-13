import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const { wavFromFloatChunks } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/voiceWav.ts"));

function tone(frequency, sampleRate, seconds, amplitude = 0.3) {
  return Float32Array.from({ length: sampleRate * seconds }, (_, index) => amplitude * Math.sin(2 * Math.PI * frequency * index / sampleRate));
}

function wavDetails(arrayBuffer) {
  const bytes = new DataView(arrayBuffer);
  return {
    channels: bytes.getUint16(22, true),
    sampleRate: bytes.getUint32(24, true),
    byteRate: bytes.getUint32(28, true),
    blockAlign: bytes.getUint16(32, true),
    bitsPerSample: bytes.getUint16(34, true),
    sampleCount: bytes.getUint32(40, true) / 2,
    samples: Float32Array.from({ length: (bytes.byteLength - 44) / 2 }, (_, index) => bytes.getInt16(44 + index * 2, true) / 32768),
  };
}

test("synthetic audio is serialized as valid 16 kHz mono 16-bit PCM WAV", async () => {
  const audio = tone(1000, 48000, 1);
  const wav = wavFromFloatChunks([audio.subarray(0, 16001), audio.subarray(16001)], 48000);
  const details = wavDetails(await wav.arrayBuffer());
  assert.equal(wav.type, "audio/wav");
  assert.equal(new TextDecoder().decode(new Uint8Array(await wav.arrayBuffer()).subarray(0, 4)), "RIFF");
  assert.equal(details.channels, 1);
  assert.equal(details.sampleRate, 16000);
  assert.equal(details.byteRate, 32000);
  assert.equal(details.blockAlign, 2);
  assert.equal(details.bitsPerSample, 16);
  assert.equal(details.sampleCount, 16000);
  const rms = Math.sqrt(details.samples.reduce((sum, sample) => sum + sample * sample, 0) / details.samples.length);
  assert.ok(rms > 0.19 && rms < 0.23, `unexpected 1 kHz RMS ${rms}`);
});

test("synthetic out-of-band tone is attenuated before 3:1 downsampling", async () => {
  const wav = wavFromFloatChunks([tone(12000, 48000, 1)], 48000);
  const { samples } = wavDetails(await wav.arrayBuffer());
  const rms = Math.sqrt(samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length);
  assert.ok(rms < 0.005, `12 kHz input aliased into the output at RMS ${rms}`);
});

test("empty microphone input is rejected", () => {
  assert.throws(() => wavFromFloatChunks([], 48000), /No microphone audio was captured/);
});
