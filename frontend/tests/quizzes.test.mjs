import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const model = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/quizModel.ts"));

test("question progress is bounded and empty quizzes stay at zero", () => {
  assert.equal(model.progressPercent(0, 4), 25);
  assert.equal(model.progressPercent(3, 4), 100);
  assert.equal(model.progressPercent(9, 4), 100);
  assert.equal(model.progressPercent(-1, 0), 0);
});

test("answered question count ignores empty and whitespace responses", () => {
  const questions = [{ attempt_id: "one" }, { attempt_id: "two" }, { attempt_id: "three" }];
  assert.equal(model.answeredCount(questions, { one: "yes", two: "  ", three: "3" }), 2);
});

test("result feedback separates strong, building, and review outcomes", () => {
  assert.equal(model.resultFeedback({ score: 4, question_count: 5 }), "strong");
  assert.equal(model.resultFeedback({ score: 3, question_count: 5 }), "building");
  assert.equal(model.resultFeedback({ score: 1, question_count: 5 }), "review");
});
