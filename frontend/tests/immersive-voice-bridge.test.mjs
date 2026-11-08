import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const { ImmersiveVoiceBridge } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/immersiveVoiceBridge.ts"));

test("immersive bridge exposes stable lesson states and rejects stale avatar generations", () => {
  const bridge = new ImmersiveVoiceBridge();
  const states = [];
  const frames = [];
  bridge.subscribe(() => states.push(bridge.getState()));
  bridge.subscribeFrames(() => frames.push(bridge.getFrame()));
  for (const state of ["listening", "thinking", "speaking", "paused", "interrupted", "error"]) bridge.setState(state);
  assert.deepEqual(states, ["listening", "thinking", "speaking", "paused", "interrupted", "error"]);
  bridge.acceptFrame({ generation: 3, state: "playing", mode: "timestamped-visemes", language: "telugu", currentTimeMs: 125, viseme: "aa" });
  assert.equal(bridge.getState(), "speaking");
  assert.equal(bridge.getFrame().currentTimeMs, 125);
  bridge.acceptFrame({ generation: 2, state: "playing", mode: "silent", language: "english", currentTimeMs: 0, viseme: "sil" });
  assert.equal(bridge.getFrame().generation, 3);
  assert.equal(frames.length, 1);
  bridge.clear();
  assert.equal(bridge.getState(), "idle");
  assert.equal(bridge.getFrame().viseme, "sil");
});
