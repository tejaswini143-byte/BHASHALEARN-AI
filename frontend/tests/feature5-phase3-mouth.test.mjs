import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const dir = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const { speechMorphWeight } = require(resolve(dir, "teacherMouth.ts"));
const { ImmersiveVoiceBridge } = require(resolve(dir, "immersiveVoiceBridge.ts"));

test("speech morphs map common rigged character mouth targets without changing unrelated expressions", () => {
  assert.equal(speechMorphWeight("jawOpen", "aa"), 0.55);
  assert.equal(speechMorphWeight("mouthFunnel", "oh"), 0.55);
  assert.equal(speechMorphWeight("viseme_ee", "ee"), 0.55);
  assert.equal(speechMorphWeight("jawOpen", "sil"), 0);
  assert.equal(speechMorphWeight("mouthFunnel", "aa"), 0);
  assert.equal(speechMorphWeight("eyeBlinkLeft", "aa"), null);
});

test("pause, interruption and errors immediately notify the mouth renderer to close", () => {
  const bridge = new ImmersiveVoiceBridge();
  let frames = 0;
  bridge.subscribeFrames(() => frames++);
  bridge.acceptFrame({ generation: 1, state: "playing", mode: "audio-driven-approximate", language: "telugu", currentTimeMs: 200, viseme: "aa" });
  bridge.setState("paused");
  assert.equal(bridge.getFrame().viseme, "sil");
  assert.equal(bridge.getState(), "paused");
  assert.equal(frames, 2);
  bridge.setState("interrupted");
  assert.equal(bridge.getFrame().viseme, "sil");
  assert.equal(frames, 3);
});

test("bridge rejects invalid playback clocks and stale generations", () => {
  const bridge = new ImmersiveVoiceBridge();
  const frame = { generation: 3, state: "playing", mode: "timestamped-visemes", language: "english", currentTimeMs: 120, viseme: "aa" };
  bridge.acceptFrame(frame);
  bridge.acceptFrame({ ...frame, generation: 2, viseme: "oh" });
  bridge.acceptFrame({ ...frame, currentTimeMs: NaN, viseme: "oh" });
  assert.equal(bridge.getFrame().viseme, "aa");
});
