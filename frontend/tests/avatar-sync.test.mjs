import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const { AvatarSyncController } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/avatarSync.ts"));
const { teacherActionsForAvatarSyncFrame } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/voiceContract.ts"));
const { ImmersiveVoiceBridge } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/immersiveVoiceBridge.ts"));

function makeController() {
  const frames = [];
  return { frames, controller: new AvatarSyncController(frame => frames.push(frame)) };
}

test("timestamped visemes use the media playback clock, including pause and resume", () => {
  const { frames, controller } = makeController();
  const generation = controller.begin({ visemes: [
    { atMs: 100, durationMs: 150, viseme: "aa" },
    { atMs: 300, durationMs: 200, viseme: "mm" },
  ] }, "english");
  controller.play(generation);
  controller.tick(generation, { currentTime: 0.2, paused: false, ended: false });
  assert.equal(frames.at(-1).viseme, "aa");
  assert.equal(frames.at(-1).currentTimeMs, 200);
  assert.equal(frames.at(-1).mode, "timestamped-visemes");
  controller.pause(generation);
  controller.tick(generation, { currentTime: 0.4, paused: true, ended: false });
  assert.equal(frames.at(-1).state, "paused");
  assert.equal(frames.at(-1).viseme, "sil");
  controller.play(generation);
  controller.tick(generation, { currentTime: 0.35, paused: false, ended: false });
  assert.equal(frames.at(-1).viseme, "mm");
});

test("missing alignment cues selects an honestly labeled audio-driven approximation", () => {
  const { frames, controller } = makeController();
  const generation = controller.begin({}, "english");
  controller.play(generation);
  controller.tick(generation, { currentTime: 0.2, paused: false, ended: false }, 0.1);
  assert.equal(frames.at(-1).mode, "audio-driven-approximate");
  assert.notEqual(frames.at(-1).viseme, "sil");
  controller.tick(generation, { currentTime: 0.22, paused: false, ended: false }, 0.001);
  assert.equal(frames.at(-1).viseme, "sil");
});

test("language profiles do not reuse the same approximate mouth mapping", () => {
  const english = makeController();
  const en = english.controller.begin({}, "english"); english.controller.play(en);
  english.controller.tick(en, { currentTime: 0, paused: false, ended: false }, 0.1);
  const telugu = makeController();
  const te = telugu.controller.begin({}, "telugu"); telugu.controller.play(te);
  telugu.controller.tick(te, { currentTime: 0, paused: false, ended: false }, 0.1);
  assert.notEqual(english.frames.at(-1).viseme, telugu.frames.at(-1).viseme);
  const mixed = makeController();
  const mx = mixed.controller.begin({}, "mixed"); mixed.controller.play(mx);
  mixed.controller.tick(mx, { currentTime: 0, paused: false, ended: false }, 0.1);
  assert.equal(mixed.frames.at(-1).language, "mixed");
});

test("cancellation invalidates stale events and a replay starts a new generation", () => {
  const { frames, controller } = makeController();
  const first = controller.begin({}, "english"); controller.play(first);
  controller.tick(first, { currentTime: 0.1, paused: false, ended: false }, 0.3);
  controller.cancel(first);
  const cancelledFrameCount = frames.length;
  controller.tick(first, { currentTime: 4, paused: false, ended: false }, 0.3);
  controller.complete(first);
  assert.equal(frames.length, cancelledFrameCount);
  assert.equal(frames.at(-1).state, "interrupted");
  assert.equal(frames.at(-1).viseme, "sil");
  const replay = controller.begin({ visemes: [{ atMs: 0, durationMs: 100, viseme: "ee" }] }, "telugu");
  assert.ok(replay > first);
  controller.play(replay);
  controller.tick(replay, { currentTime: 0.02, paused: false, ended: false });
  assert.equal(frames.at(-1).viseme, "ee");
  assert.equal(frames.at(-1).language, "telugu");
});

test("completion and playback failures stop mouth motion and map to teacher idle", () => {
  const { frames, controller } = makeController();
  const generation = controller.begin({}, "english"); controller.play(generation);
  controller.tick(generation, { currentTime: 0.1, paused: false, ended: true }, 0.4);
  assert.equal(frames.at(-1).state, "completed");
  assert.equal(frames.at(-1).viseme, "sil");
  assert.deepEqual(teacherActionsForAvatarSyncFrame(frames.at(-1)), [{ type: "teacher_state", state: "idle" }]);
  const failedGeneration = controller.begin({}, "english"); controller.play(failedGeneration); controller.fail(failedGeneration);
  controller.tick(failedGeneration, { currentTime: 2, paused: false, ended: false }, 0.8);
  assert.equal(frames.at(-1).state, "error");
  assert.equal(frames.at(-1).viseme, "sil");
});

test("phoneme timing can drive coarse existing viseme shapes without claiming exact shapes", () => {
  const { frames, controller } = makeController();
  const generation = controller.begin({ phonemes: [{ atMs: 0, durationMs: 100, phoneme: "m" }] }, "english");
  controller.play(generation);
  controller.tick(generation, { currentTime: 0.04, paused: false, ended: false });
  assert.equal(frames.at(-1).mode, "timestamped-phonemes-approximate");
  assert.equal(frames.at(-1).viseme, "mm");
  assert.throws(() => controller.begin({ phonemes: [{ atMs: -1, durationMs: 0, phoneme: "m" }] }, "english"), /Invalid phoneme timeline/);
});

test("playback and pause states bridge to the existing teacher interface", () => {
  const { frames, controller } = makeController();
  const generation = controller.begin({ visemes: [{ atMs: 0, durationMs: 200, viseme: "aa" }] }, "telugu");
  controller.play(generation);
  controller.tick(generation, { currentTime: 0.04, paused: false, ended: false });
  assert.deepEqual(teacherActionsForAvatarSyncFrame(frames.at(-1)).map(command => command.type), ["teacher_state", "teacher_action"]);
  controller.pause(generation);
  assert.deepEqual(teacherActionsForAvatarSyncFrame(frames.at(-1)), [{ type: "teacher_state", state: "idle" }]);
});


test("immersive bridge shares playback frames without per-frame React-style notifications", () => {
  const bridge = new ImmersiveVoiceBridge();
  let notifications = 0;
  let frameNotifications = 0;
  bridge.subscribe(() => { notifications += 1; });
  bridge.subscribeFrames(() => { frameNotifications += 1; });
  const speaking = { generation: 2, state: "playing", mode: "audio-driven-approximate", language: "mixed", currentTimeMs: 100, viseme: "aa" };
  bridge.acceptFrame(speaking);
  bridge.acceptFrame({ ...speaking, currentTimeMs: 215, viseme: "ee" });
  assert.equal(bridge.getState(), "speaking");
  assert.equal(bridge.getFrame().currentTimeMs, 215);
  assert.equal(bridge.getFrame().viseme, "ee");
  assert.equal(notifications, 1, "listeners update only when teacher state changes");
  assert.equal(frameNotifications, 2, "the renderer can schedule frames without React state updates");
  bridge.setState("listening");
  assert.equal(bridge.getState(), "listening");
  assert.equal(bridge.getFrame().viseme, "sil");
  bridge.acceptFrame({ ...speaking, generation: 3, currentTimeMs: 20, viseme: "oh" });
  bridge.acceptFrame({ ...speaking, generation: 2, currentTimeMs: 900, viseme: "aa" });
  assert.equal(bridge.getFrame().generation, 3, "older utterance callbacks cannot replace a newer frame");
  bridge.setState("thinking");
  bridge.setState("error");
  bridge.clear();
  assert.equal(bridge.getState(), "idle");
  assert.equal(bridge.getFrame().viseme, "sil");
});

test("controller uses media-time fallback for all supported languages without Web Audio", () => {
  const result = language => {
    const { frames, controller } = makeController();
    const generation = controller.begin({}, language);
    controller.play(generation);
    controller.tick(generation, { currentTime: 0.15, paused: false, ended: false });
    return frames.at(-1);
  };
  for (const language of ["english", "telugu", "mixed"]) {
    const frame = result(language);
    assert.equal(frame.language, language);
    assert.equal(frame.mode, "audio-driven-approximate");
    assert.notEqual(frame.viseme, "sil");
  }
});
