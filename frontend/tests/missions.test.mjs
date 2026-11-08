import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const model = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/missionModel.ts"));

const sample = (overrides = {}) => ({
  id: "quest-fractions", title: "Fraction Explorer", subject: "Mathematics", description: "Practice fractions",
  objective: "Answer 3 questions", progress: 1, target: 3, xp_reward: 60, completed: false, eligible: false,
  completed_at: null, daily: false, active_date: null, ...overrides,
});

test("mission progress states render as in-progress, ready, and claimed", () => {
  assert.equal(model.missionState(sample()), "in-progress");
  assert.equal(model.missionState(sample({ progress: 3, eligible: true })), "ready");
  assert.equal(model.missionState(sample({ completed: true, eligible: false })), "claimed");
});

test("mission progress percentage is deterministic and clamped", () => {
  assert.equal(model.progressPercent({ progress: 1, target: 3 }), 33);
  assert.equal(model.progressPercent({ progress: 8, target: 3 }), 100);
  assert.equal(model.progressPercent({ progress: -1, target: 3 }), 0);
  assert.equal(model.progressPercent({ progress: 1, target: 0 }), 0);
});
