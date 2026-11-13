import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import ts from "typescript";

const require = createRequire(import.meta.url);
const filename = new URL("../src/futureSeekerContract.ts", import.meta.url);
const compiled = ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const module = { exports: {} };
new Function("module", "exports", "require", compiled)(module, module.exports, require);
const { buildFutureSeekerHandoff, validateFutureSeekerHandoff } = module.exports;

test("valid reflection handoff has an explicit non-verified provenance", () => {
  const result = buildFutureSeekerHandoff("scientist", 2, ["Observation", "Observation", "Communication"]);
  assert.deepEqual(result.observedSkills, ["Observation", "Communication"]);
  assert.equal(result.source, "illustrative-simulation");
  assert.equal(result.version, 1);
});
test("untrusted handoffs reject unsupported careers, malformed progress and forged provenance", () => {
  const valid = buildFutureSeekerHandoff("doctor", 1, ["Listening"]);
  for (const bad of [{ ...valid, careerId: "admin" }, { ...valid, completedSteps: -1 }, { ...valid, source: "verified" }, { ...valid, observedSkills: ["A", "A"] }, null]) {
    assert.throws(() => validateFutureSeekerHandoff(bad), /Invalid Future Seeker handoff/);
  }
});
