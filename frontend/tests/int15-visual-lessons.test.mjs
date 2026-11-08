import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const sourceDir = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const model = require(resolve(sourceDir, "visualLessonsModel.ts"));

test("visual lesson catalog has structured objectives, steps, takeaways and English/Telugu copy", () => {
  assert.deepEqual(model.visualLessons.map(lesson => lesson.id), ["solar-system", "geometry", "pendulum"]);
  for (const lesson of model.visualLessons) {
    assert.ok(lesson.subject.en && lesson.subject.te && lesson.topic.en && lesson.topic.te);
    assert.ok(lesson.title.en && lesson.title.te && lesson.description.en && lesson.description.te);
    assert.ok(lesson.objectives.length >= 1 && lesson.takeaways.length >= 1 && lesson.steps.length >= 3);
    for (const item of [...lesson.objectives, ...lesson.takeaways, ...lesson.steps.flatMap(step => [step.title, step.explanation])]) assert.ok(item.en && item.te);
  }
  assert.equal(model.solarPlanets.length, 8);
  assert.ok(model.solarPlanets.every(planet => planet.name.en && planet.name.te && planet.description.en && planet.description.te));
});

test("solar orbit math scales elapsed days and handles zero and invalid time", () => {
  const mercury = model.solarPlanets[0];
  assert.deepEqual(model.planetPosition(mercury, 0, 30), [mercury.orbit, 0]);
  assert.deepEqual(model.planetPosition(mercury, 100, 0), [mercury.orbit, 0]);
  const [quarterX, quarterZ] = model.planetPosition(mercury, mercury.orbitalDays / 4, 1);
  assert.ok(Math.abs(quarterX) < 1e-10);
  assert.ok(Math.abs(quarterZ - mercury.orbit) < 1e-10);
  assert.deepEqual(model.planetPosition(mercury, Number.NaN, 4), [mercury.orbit, 0]);
});

test("geometry calculations report shape features, formulas, area, and volume", () => {
  assert.deepEqual(model.shapeMeasurements("cube", 2), { faces: 6, edges: 12, vertices: 8, formula: "V = a³", volume: 8, surfaceArea: 24 });
  const sphere = model.shapeMeasurements("sphere", 1);
  assert.equal(sphere.faces, 0); assert.equal(sphere.edges, 0); assert.equal(sphere.vertices, 0);
  assert.ok(Math.abs(sphere.volume - 4 * Math.PI / 3) < 1e-12);
  const cylinder = model.shapeMeasurements("cylinder", 2);
  assert.equal(cylinder.faces, 3); assert.equal(cylinder.edges, 2); assert.equal(cylinder.vertices, 0);
  assert.ok(Math.abs(cylinder.volume - 16 * Math.PI) < 1e-12);
  assert.throws(() => model.shapeMeasurements("cube", 0), /positive finite/);
  assert.throws(() => model.shapeMeasurements("pyramid", 1), /Unsupported shape/);
});

test("pendulum period follows the small-angle formula and rejects invalid inputs", () => {
  const standardEarth = model.pendulumPeriod(1, 9.81);
  assert.ok(Math.abs(standardEarth - 2.00606668) < 1e-6);
  assert.ok(Math.abs(model.pendulumPeriod(4, 9.81) / standardEarth - 2) < 1e-12);
  assert.ok(model.pendulumPeriod(1, 4) > standardEarth);
  for (const [length, gravity] of [[0, 9.81], [-1, 9.81], [1, 0], [1, -2], [Infinity, 9.81], [1, Number.NaN]]) assert.throws(() => model.pendulumPeriod(length, gravity), /positive finite/);
});

test("visual control reducer selects, advances, pauses, resumes, bounds invalid inputs, and resets", () => {
  const { visualControlsReducer: reduce, initialVisualControls: initial } = model;
  let state = reduce(initial, { type: "lesson", id: "pendulum" });
  assert.equal(state.lessonId, "pendulum");
  state = reduce(state, { type: "play" }); assert.equal(state.playing, true);
  state = reduce(state, { type: "pause" }); assert.equal(state.playing, false);
  state = reduce(state, { type: "step", delta: 1, stepCount: 3 }); assert.equal(state.step, 0);
  state = reduce(state, { type: "step", delta: 20, stepCount: 3 }); assert.equal(state.step, 2);
  state = reduce(state, { type: "length", value: 999 }); assert.equal(state.length, 3);
  const unchanged = reduce(state, { type: "gravity", value: Number.NaN }); assert.equal(unchanged, state);
  assert.equal(reduce(state, { type: "planet", id: "unknown" }), state);
  state = reduce(state, { type: "reset" });
  assert.equal(state.lessonId, "pendulum"); assert.equal(state.playing, false); assert.equal(state.step, -1); assert.equal(state.length, initial.length);
});

test("accessible unavailable-device fallback and reduced-motion mode are present", async () => {
  const [component, styles] = await Promise.all([
    readFile(resolve(sourceDir, "VisualLessons.tsx"), "utf8"),
    readFile(resolve(sourceDir, "visual-lessons.css"), "utf8"),
  ]);
  assert.match(component, /3D simulation unavailable/);
  assert.match(component, /fallback=\{<SimulationFallback\/>\}/);
  assert.match(component, /frameloop=\{reduced \? "demand" : "always"\}/);
  assert.match(component, /prefers-reduced-motion: reduce/);
  assert.match(styles, /@media\(prefers-reduced-motion:reduce\)/);
});
