import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const model = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/personalizedTeaching.ts"));

const validPlan = {
  session_id: "s1", evidence_attempts: 0, mastery_score: null, recommendation_source: "no_history", learning_goal: null, citations: [],
  plan: { learning_objective: "Explain halves", prerequisite_concepts: [], explanation_strategy: "Use a picture", examples: ["A cut apple"], understanding_checks: ["What is half?"], suggested_next_activity: "Try a question", difficulty: "beginner", language: "mixed", recommended_topic: null, recommendation_reason: "No history yet.", fallback: true, grounded: false },
};

test("personalized lesson contract accepts stable beginner and bilingual plans", () => {
  assert.equal(model.validatePersonalizedLesson(validPlan).plan.language, "mixed");
  assert.equal(model.validatePersonalizedLesson(validPlan).plan.difficulty, "beginner");
  assert.throws(() => model.validatePersonalizedLesson({ ...validPlan, plan: { ...validPlan.plan, examples: [] } }), /validation/);
});

test("only explicit confusion phrases trigger the simpler explanation signal", () => {
  assert.equal(model.isExplicitConfusion("I'm confused about this step"), true);
  assert.equal(model.isExplicitConfusion("I got the answer right"), false);
});

test("classroom renders loading, error, fallback, check, and adjustment actions accessibly", async () => {
  const component = await readFile(new URL("../src/PersonalizedLessonPlan.tsx", import.meta.url), "utf8");
  const classroom = await readFile(new URL("../src/Classroom.tsx", import.meta.url), "utf8");
  assert.ok(classroom.includes("<PersonalizedLessonPlan"));
  assert.ok(component.includes('role="status"'));
  assert.ok(component.includes('role="alert"'));
  assert.ok(component.includes("Explain more simply"));
  assert.ok(component.includes("Give another example"));
  assert.ok(component.includes("Review prerequisites"));
  assert.ok(component.includes('htmlFor="cl-understanding-answer"'));
});
