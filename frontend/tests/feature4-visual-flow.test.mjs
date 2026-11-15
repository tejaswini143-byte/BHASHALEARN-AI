import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const source = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const { visualLessons } = require(resolve(source, "visualLessonsModel.ts"));
const { validateGeneratedVisualLessonEnvelope } = require(resolve(source, "visualLessonContract.ts"));

test("React Flow smartboard binds lesson steps to highlights and explanations", () => {
  const board = readFileSync(resolve(source, "VisualFlowBoard.tsx"), "utf8");
  assert.match(board, /from "@xyflow\/react"/);
  assert.match(board, /onNodeClick/);
  assert.match(board, /onStepChange\(index\)/);
  assert.match(board, /current\.explanation\[language\]/);
  assert.match(board, /<Controls\s*\/>/);
  assert.match(board, /<MiniMap/);
  assert.match(board, /Reset and replay/);
  assert.match(board, /\/tutor\/sessions\//);
  assert.match(board, /Student question:/);
  assert.match(board, /sessionId/);
});

test("version 2 generation schema accepts only allowlisted lesson scenes and safe parameters", () => {
  const base = visualLessons[0];
  const valid = {
    version: 2,
    lesson: {
      ...base,
      steps: base.steps.map(step => ({ ...step, scene_id: base.id })),
      questions: [{ prompt: base.title, answer: base.title, explanation: base.description }],
      activities: [{ instruction: base.description, control: "select-planet" }],
      completion_criteria: [base.description],
    },
    scene: { kind: "solar-system", parameters: { time_scale: 30 } },
  };
  assert.equal(validateGeneratedVisualLessonEnvelope(valid).version, 2);
  assert.throws(() => validateGeneratedVisualLessonEnvelope({ ...valid, scene: { kind: "geometry", parameters: { shape: "cube", size: 1 } } }), /does not match/);
  assert.throws(() => validateGeneratedVisualLessonEnvelope({ ...valid, scene: { kind: "solar-system", parameters: { command: "eval" } } }), /parameters are invalid/);
  assert.throws(() => validateGeneratedVisualLessonEnvelope({ ...valid, lesson: { ...valid.lesson, activities: [{ instruction: base.description, control: "execute-code" }] } }), /activities are invalid/);
});
