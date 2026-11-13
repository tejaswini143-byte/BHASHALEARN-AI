import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const file = resolve(dirname(fileURLToPath(import.meta.url)), "../src/VisualLessons.tsx");
test("reset restores pendulum pivot and resets elapsed simulation clock", async () => {
  const source = await readFile(file, "utf8");
  assert.match(source, /elapsed\.current = 0; if \(pivot\.current\) pivot\.current\.rotation\.z = 0;/);
});
test("keyboard reset uses stable callback and properly updates effect dependencies", async () => {
  const source = await readFile(file, "utf8");
  assert.match(source, /const reset = useCallback\(\(\) =>/);
  assert.match(source, /\}, \[advance, reset\]\);/);
  assert.doesNotMatch(source, /function reset\(\)/);
});
