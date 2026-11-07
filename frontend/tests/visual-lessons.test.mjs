import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
require.extensions[".tsx"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
require.extensions[".css"] = () => {};
const sourceDir = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const engine = require(resolve(sourceDir, "lessonEngine.ts"));
const { InteractiveLessonStudio } = require(resolve(sourceDir, "InteractiveLessonStudio.tsx"));

test("all three sample lessons validate and provide a scored exercise", () => {
  assert.equal(engine.sampleLessons.length, 3);
  for (const lesson of engine.sampleLessons) {
    assert.equal(engine.validateLessonPlan(lesson).id, lesson.id);
    assert.ok(lesson.steps.length >= 3);
    assert.ok(lesson.exercise.choices.includes(lesson.exercise.answer));
  }
  assert.match(engine.sampleLessons[0].title, /Pythagorean/);
  assert.match(engine.sampleLessons[1].title, /solar system/i);
  assert.match(engine.sampleLessons[2].title, /Telugu/i);
});

test("lesson validation rejects unsupported commands, unknown targets and invalid choices", () => {
  const valid = structuredClone(engine.sampleLessons[0]);
  valid.steps[0].commands.push({ type: "highlight", id: "missing" });
  assert.throws(() => engine.validateLessonPlan(valid), /unknown object/);
  const unsupported = structuredClone(engine.sampleLessons[0]);
  unsupported.steps[0].commands.push({ type: "speak", text: "hello" });
  assert.throws(() => engine.validateLessonPlan(unsupported), /unsupported command/);
  const invalidExercise = structuredClone(engine.sampleLessons[0]);
  invalidExercise.exercise.answer = "Not an option";
  assert.throws(() => engine.validateLessonPlan(invalidExercise), /exercise is invalid/);
});

test("lesson playback steps deterministically through play, pause, previous, next and replay", () => {
  const count = engine.sampleLessons[0].steps.length;
  let playback = { step: -1, playing: false };
  playback = engine.playbackReducer(playback, "play", count);
  assert.deepEqual(playback, { step: -1, playing: true });
  playback = engine.playbackReducer(playback, "tick", count);
  assert.deepEqual(playback, { step: 0, playing: true });
  playback = engine.playbackReducer(playback, "pause", count);
  assert.equal(playback.playing, false);
  playback = engine.playbackReducer(playback, "next", count);
  assert.equal(playback.step, 1);
  playback = engine.playbackReducer(playback, "previous", count);
  assert.equal(playback.step, 0);
  playback = engine.playbackReducer({ step: count - 1, playing: false }, "play", count);
  assert.deepEqual(playback, { step: -1, playing: true });
  playback = engine.playbackReducer(playback, "replay", count);
  assert.deepEqual(playback, { step: -1, playing: false });
});

test("board history restores moves and erasures while student drawings stay separate", () => {
  const initial = engine.sampleLessons[0].objects;
  const originalX = initial[0].x;
  let state = engine.createBoardState(initial);
  state = engine.boardReducer(state, { type: "add-student", object: { id: "sketch", shape: "path", x: 12, y: 8, points: [{ x: 12, y: 8 }] } });
  state = engine.boardReducer(state, { type: "snapshot" });
  state = engine.boardReducer(state, { type: "move-object", id: initial[0].id, x: 700, y: 400 });
  assert.equal(state.authored[0].x, 700);
  assert.equal(state.student.length, 1);
  state = engine.boardReducer(state, { type: "undo", initial });
  assert.equal(state.authored[0].x, originalX);
  assert.equal(state.student.length, 1);
  state = engine.boardReducer(state, { type: "redo", initial });
  assert.equal(state.authored[0].x, 700);
  state = engine.boardReducer(state, { type: "erase-object", id: "sketch" });
  assert.equal(state.student.length, 0);
  state = engine.boardReducer(state, { type: "undo", initial });
  assert.equal(state.student.length, 1);
  state = engine.boardReducer(state, { type: "reset", initial });
  assert.equal(state.student.length, 0);
  assert.equal(state.authored[0].x, originalX);
});

test("future lesson envelope validates versioned plans and gesture target ids", () => {
  const plan = engine.sampleLessons[0];
  assert.equal(engine.validateLessonEnvelope({ version: 1, plan, gestureIntents: [{ gesture: "point", targetObjectId: "triangle", durationMs: 500 }] }).version, 1);
  assert.throws(() => engine.validateLessonEnvelope({ version: 2, plan }), /version/);
  assert.throws(() => engine.validateLessonEnvelope({ version: 1, plan, gestureIntents: [{ gesture: "point", targetObjectId: "absent" }] }), /unknown target/);
});

test("smartboard component renders accessible tools, live canvas, lesson player and exercise", () => {
  const html = renderToStaticMarkup(React.createElement(InteractiveLessonStudio));
  for (const label of ["Select and move", "Draw freely", "Erase object", "Highlight object", "Pan board", "Undo", "Redo", "Reset board", "Zoom in", "Sample lesson", "Interactive smartboard", "Play lesson", "Previous lesson step", "Next lesson step", "Check answer"]) assert.ok(html.includes(label), `missing smartboard UI: ${label}`);
  assert.match(html, /<svg[^>]+role="application"/);
  assert.match(html, /Your private marks/);
  assert.match(html, /a² \+ b² = c²/);
});
