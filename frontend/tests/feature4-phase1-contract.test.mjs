import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
const source = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const { visualLessons } = require(resolve(source, "visualLessonsModel.ts"));
const { createVisualLessonEnvelope, validateVisualLessonEnvelope } = require(resolve(source, "visualLessonContract.ts"));

test("every existing bilingual simulation has a versioned, valid visual lesson contract", () => {
  assert.equal(visualLessons.length, 3);
  for (const lesson of visualLessons) {
    const envelope = createVisualLessonEnvelope(lesson);
    assert.equal(envelope.version, 1);
    assert.equal(envelope.scene.kind, lesson.id);
    assert.deepEqual(validateVisualLessonEnvelope(envelope), envelope);
  }
});

test("visual lesson contract rejects invalid versions and mismatched scene ids", () => {
  const valid = createVisualLessonEnvelope(visualLessons[0]);
  assert.throws(() => validateVisualLessonEnvelope({ ...valid, version: 2 }), /version/);
  assert.throws(() => validateVisualLessonEnvelope({ ...valid, scene: { kind: "geometry" } }), /does not match/);
  assert.throws(() => validateVisualLessonEnvelope({ ...valid, lesson: { ...valid.lesson, id: "unknown" } }), /Unsupported visual lesson id/);
});

test("visual lesson contract rejects missing Telugu content and empty lesson steps", () => {
  const valid = createVisualLessonEnvelope(visualLessons[0]);
  assert.throws(() => validateVisualLessonEnvelope({ ...valid, lesson: { ...valid.lesson, title: { en: "English", te: " " } } }), /bilingual metadata/);
  assert.throws(() => validateVisualLessonEnvelope({ ...valid, lesson: { ...valid.lesson, steps: [] } }), /steps/);
});
