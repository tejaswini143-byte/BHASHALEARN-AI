import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const client = readFileSync(new URL("../src/visualLessonsApi.ts", import.meta.url), "utf8");
const view = readFileSync(new URL("../src/VisualLessons.tsx", import.meta.url), "utf8");

test("catalog requests use authenticated API and validate every envelope", () => {
  assert.match(client, /Authorization:/);
  assert.match(client, /validateVisualLessonEnvelope/);
  assert.match(client, /Duplicate visual lesson IDs/);
});
test("workspace hydrates lessons and retains local fallback on failure", () => {
  assert.match(view, /fetchVisualLessonCatalog\(token, controller.signal\)/);
  assert.match(view, /useState<VisualLesson\[]>\(visualLessons\)/);
  assert.match(view, /visualLessonApiError\(error\)/);
  assert.match(view, /controller.abort\(\)/);
});
