import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(
  ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText, filename
);
const { AvatarSyncController } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/avatarSync.ts"));

test("invalid viseme timeline does not replace current teacher playback", () => {
  const frames = [];
  const controller = new AvatarSyncController(frame => frames.push(frame));
  const active = controller.begin({ visemes: [{ atMs: 0, durationMs: 100, viseme: "aa" }] }, "english");
  controller.play(active);
  assert.throws(() => controller.begin({ visemes: [
    { atMs: 0, durationMs: 100, viseme: "aa" },
    { atMs: 50, durationMs: 100, viseme: "ee" },
  ] }, "english"), /Invalid viseme timeline/);
  assert.equal(controller.currentGeneration(), active);
  assert.equal(controller.currentState(), "playing");
  controller.tick(active, { currentTime: 0.05, paused: false, ended: false });
  assert.equal(frames.at(-1).viseme, "aa");
});

test("invalid phonemes and languages cannot corrupt active playback", () => {
  const controller = new AvatarSyncController(() => {});
  const active = controller.begin({}, "telugu");
  assert.throws(() => controller.begin({ phonemes: [
    { atMs: 0, durationMs: 100, phoneme: "a" },
    { atMs: 70, durationMs: 100, phoneme: "e" },
  ] }, "telugu"), /Invalid phoneme timeline/);
  assert.throws(() => controller.begin({}, "unknown"), /Invalid sync language/);
  assert.equal(controller.currentGeneration(), active);
});

test("interruption silences the avatar and rejects stale playback frames", () => {
  const frames = [];
  const controller = new AvatarSyncController(frame => frames.push(frame));
  const active = controller.begin({}, "mixed");
  controller.play(active);
  controller.tick(active, { currentTime: 0.2, paused: false, ended: false }, 0.3);
  controller.cancel(active);
  assert.equal(frames.at(-1).viseme, "sil");
  assert.equal(frames.at(-1).state, "interrupted");
  const length = frames.length;
  controller.tick(active, { currentTime: 0.3, paused: false, ended: false }, 0.3);
  assert.equal(frames.length, length);
});
