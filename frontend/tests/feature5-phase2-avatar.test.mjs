import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
const sourceDir = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const { validateAvatarFile, MAX_AVATAR_BYTES, hasRiggedCharacter } = require(resolve(sourceDir, "avatarAsset.ts"));

test("local avatar import rejects empty, oversized and non-GLB files", () => {
  assert.throws(() => validateAvatarFile({ name: "avatar.png", size: 200 }), /glb/);
  assert.throws(() => validateAvatarFile({ name: "teacher.glb", size: 0 }), /empty/);
  assert.throws(() => validateAvatarFile({ name: "teacher.glb", size: MAX_AVATAR_BYTES + 1 }), /25 MB/);
  assert.doesNotThrow(() => validateAvatarFile({ name: "teacher.GLB", size: 1024 }));
});

test("only skinned character models qualify as rigged teacher avatars", () => {
  assert.equal(hasRiggedCharacter({ scene: { traverse: visit => visit({ isSkinnedMesh: false }) }, clips: [] }), false);
  assert.equal(hasRiggedCharacter({ scene: { traverse: visit => visit({ isSkinnedMesh: true }) }, clips: [] }), true);
});

test("immersive classroom has accessible avatar import, error and removal controls", async () => {
  const [scene, preview, css] = await Promise.all(["ImmersiveClassroom.tsx", "TeacherPreview.tsx", "immersive-classroom.css"].map(name => readFile(resolve(sourceDir, name), "utf8")));
  assert.match(scene, /Upload rigged GLB teacher/);
  assert.match(scene, /role="alert"/);
  assert.match(scene, /Remove teacher/);
  assert.match(scene, /model=\{avatar\}/);
  assert.match(preview, /model=\{model\}/);
  assert.match(css, /pointer-events: auto/);
});
