import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
const sourceDir = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const core = require(resolve(sourceDir, "immersiveCore.ts"));
const engine = require(resolve(sourceDir, "lessonEngine.ts"));

test("immersive route is separate and checks the authenticated student before rendering", async () => {
  const [app, scene] = await Promise.all([
    readFile(resolve(sourceDir, "App.tsx"), "utf8"),
    readFile(resolve(sourceDir, "ImmersiveClassroom.tsx"), "utf8"),
  ]);
  assert.ok(app.includes('path="/immersive"'));
  assert.ok(scene.includes("getCurrentStudent(token)"));
  assert.ok(scene.includes('navigate("/login"'));
  assert.ok(scene.includes('role="alert"'));
});

test("camera presets cover overview, teacher and lesson focus", () => {
  assert.deepEqual(Object.keys(core.cameraPresets), ["overview", "teacher", "lesson"]);
  for (const preset of Object.values(core.cameraPresets)) {
    assert.equal(preset.position.length, 3);
    assert.equal(preset.target.length, 3);
    assert.ok(preset.position.every(Number.isFinite));
  }
});

test("scene controls include keyboard, reduced motion and an accessible WebGL fallback", async () => {
  const scene = await readFile(resolve(sourceDir, "ImmersiveClassroom.tsx"), "utf8");
  assert.ok(scene.includes("ArrowRight"));
  assert.ok(scene.includes("ArrowLeft"));
  assert.ok(scene.includes('event.key.toLowerCase() === "f"'));
  assert.ok(scene.includes("prefers-reduced-motion: reduce"));
  assert.ok(scene.includes('frameloop={reduced ? "demand" : "always"}'));
  assert.ok(scene.includes("speed={reduced ? 0 : 0.12}"));
  assert.ok(scene.includes('role="alert" aria-label="3D scene unavailable"'));
  assert.ok(scene.includes('fallback={<WebGLFallback/>}'));
});

test("lesson steps focus their holographic objects and the scene uses no conventional presentation surface", async () => {
  const lesson = engine.sampleLessons[0];
  assert.deepEqual(core.focusedLessonObjectIds(lesson, 0), ["triangle"]);
  assert.deepEqual(core.focusedLessonObjectIds(lesson, 1), ["side-a", "side-b", "sum"]);
  assert.deepEqual(core.focusedLessonObjectIds(lesson, -1), []);
  const scene = await readFile(resolve(sourceDir, "ImmersiveClassroom.tsx"), "utf8");
  const world = scene.slice(scene.indexOf("function ImmersiveRoom"), scene.indexOf("function CameraDirector"));
  assert.ok(!/smartboard|whiteboard|projector|board-shaped/i.test(world));
  assert.ok(world.includes("circleGeometry"));
  assert.ok(!world.includes("boxGeometry"));
});
