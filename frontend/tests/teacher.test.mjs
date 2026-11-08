import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const core = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/teacherCore.ts"));

test("teacher states are exclusive and transient movement settles to idle", () => {
  assert.equal(core.transitionTeacher("idle", "point"), "point");
  assert.equal(core.settledTeacherState("walk"), "idle");
  assert.equal(core.settledTeacherState("listen"), "listen");
  assert.throws(() => core.transitionTeacher("idle", "fly"), /Unknown teacher state/);
});

test("teacher actions validate coordinates and supported actions", () => {
  assert.equal(core.validateTeacherAction({ type: "walkTo", x: 0, z: -2 }).type, "walkTo");
  assert.throws(() => core.validateTeacherAction({ type: "lookAt", x: NaN, y: 1, z: 0 }), /finite/);
  assert.throws(() => core.validateTeacherAction({ type: "gesture", name: "spin" }), /Unknown gesture/);
  assert.throws(() => core.validateTeacherAction({ type: "explain", durationMs: 0 }), /positive/);
});

test("normalized smartboard coordinates map to the classroom board plane", () => {
  assert.deepEqual(core.mapBoardTarget({ x: 0, y: 0 }), [-3, 1.6875, -4.8]);
  assert.deepEqual(core.mapBoardTarget({ x: 1, y: 1 }), [3, -1.6875, -4.8]);
  assert.deepEqual(core.mapBoardTarget({ x: 0.5, y: 0.5 }), [0, 0, -4.8]);
  assert.throws(() => core.mapBoardTarget({ x: 1.1, y: 0.5 }), /normalized/);
});

test("viseme timelines validate and select timed mouth shapes", () => {
  const timeline = [{ atMs: 0, durationMs: 120, viseme: "aa" }, { atMs: 120, durationMs: 80, viseme: "mm" }];
  assert.equal(core.visemeAt(timeline, 50), "aa");
  assert.equal(core.visemeAt(timeline, 160), "mm");
  assert.equal(core.visemeAt(timeline, 220), "sil");
  assert.throws(() => core.validateVisemeTimeline([{ atMs: 100, durationMs: 10, viseme: "aa" }, { atMs: 90, durationMs: 10, viseme: "ee" }]), /Invalid/);
});

test("teacher route exposes WebGL, loading and honest avatar fallbacks", async () => {
  const [app, component] = await Promise.all([
    readFile(new URL("../src/App.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/TeacherPreview.tsx", import.meta.url), "utf8"),
  ]);
  assert.ok(app.includes('path="/teacher"'));
  assert.ok(component.includes("<Canvas"));
  assert.ok(component.includes("WebGL preview unavailable"));
  assert.ok(component.includes("Articulated geometric fallback"));
  assert.ok(component.includes("Loading local model"));
  assert.ok(component.includes("synthetic viseme demo"));
});
