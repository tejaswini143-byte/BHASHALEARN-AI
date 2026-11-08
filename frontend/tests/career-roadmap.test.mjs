import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const model = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/careerModel.ts"));
const sample = (overrides = {}) => ({
  goal_id: "goal", career_key: "software-developer", career_title: "Software developer", summary: "General path", summary_te: "సాధారణ మార్గం", language: "mixed",
  phases: [], weekly_plan: [], total_estimated_hours: 0, planner: "deterministic_catalog_fallback", skill_gaps: [], progress: { completed_milestones: 0, total_milestones: 0 }, ...overrides,
});

test("career roadmap completion percentage handles empty and completed plans", () => {
  assert.equal(model.percentComplete(sample()), 100);
  assert.equal(model.percentComplete(sample({ progress: { completed_milestones: 1, total_milestones: 4 } })), 25);
  assert.equal(model.percentComplete(sample({ progress: { completed_milestones: 8, total_milestones: 4 } })), 100);
});

test("skill gap labels localize without translating technical keys", () => {
  assert.equal(model.gapLabel("self_reported", "english"), "Self-reported");
  assert.equal(model.gapLabel("already_demonstrated", "telugu"), "నైపుణ్యం ప్రదర్శించారు");
  assert.equal(model.gapLabel("new-status", "telugu"), "new-status");
});
