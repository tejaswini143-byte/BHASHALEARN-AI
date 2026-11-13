import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const source = resolve(dirname(fileURLToPath(import.meta.url)), "../src/ImmersiveClassroom.tsx");
test("immersive lessons expose a keyboard-operable scored check with non-spoiler feedback", async () => {
  const scene = await readFile(source, "utf8");
  assert.match(scene, /aria-label="Lesson knowledge check"/);
  assert.match(scene, /type="radio"/);
  assert.match(scene, /lesson\.exercise\.choices\.map/);
  assert.match(scene, /exerciseChoice === lesson\.exercise\.answer/);
  assert.match(scene, /role="status"/);
  assert.match(scene, /setExerciseChecked\(false\)/);
  assert.match(scene, /disabled=\{!exerciseChoice\}/);
});
