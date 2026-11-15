import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const component = readFileSync(fileURLToPath(new URL("../src/FutureMeSimulator.tsx", import.meta.url)), "utf8");
const api = readFileSync(fileURLToPath(new URL("../src/futureSeekerApi.ts", import.meta.url)), "utf8");

test("save is opt-in, after completion, and displays response feedback", () => {
  assert.match(component, /complete && <div className="fm-complete"/);
  assert.match(component, /onClick={saveReflection}/);
  assert.match(component, /disabled={saving \|\| Boolean\(savedReflectionId\)}/);
  assert.match(component, /role="status" aria-live="polite"/);
  assert.match(component, /It is not a skill assessment or career prediction/);
});
test("authenticated API request reuses the versioned bounded contract", () => {
  assert.match(api, /buildFutureSeekerHandoff\(careerId, completedSteps, skills\)/);
  assert.match(api, /Authorization: `Bearer \$\{token\}`/);
  assert.match(api, /"\/future-seeker\/reflections"/);
  assert.match(api, /method: "POST"/);
});
