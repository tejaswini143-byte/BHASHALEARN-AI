import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const contract = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/voiceContract.ts"));

test("mock transport emits deterministic bilingual recognition and synthesis events", async () => {
  const provider = new contract.MockVoiceTransport();
  const recognized = [];
  for await (const event of provider.recognize({ sessionId: "s1", language: "mixed", audio: new Blob(["test"]) })) recognized.push(event);
  assert.deepEqual(recognized.map(event => event.type), ["recognition_started", "transcript_partial", "transcript_final"]);
  assert.equal(recognized.at(-1).text, "\u0C28\u0C2E\u0C38\u0C4D\u0C15\u0C3E\u0C30\u0C02! Hello, let us learn fractions.");
  const spoken = [];
  for await (const event of provider.synthesize({ sessionId: "s1", language: "mixed", text: recognized.at(-1).text })) spoken.push(event);
  assert.deepEqual(spoken.map(event => event.type), ["synthesis_started", "audio_ready"]);
  assert.equal(spoken.at(-1).audio.url, "mock://timbre/reply.wav");
  assert.equal(spoken.at(-1).audio.visemes, undefined);
});

test("aborted mock provider calls report typed interruption errors", async () => {
  const provider = new contract.MockVoiceTransport();
  const controller = new AbortController(); controller.abort();
  const events = [];
  for await (const event of provider.recognize({ sessionId: "s1", language: "telugu", audio: new Blob(["test"]) }, controller.signal)) events.push(event);
  assert.equal(events[0].type, "recognition_failed");
  assert.equal(events[0].error.code, "interrupted");
});

test("aborted mock Timbre synthesis reports a retryable interruption without audio", async () => {
  const provider = new contract.MockVoiceTransport();
  const controller = new AbortController(); controller.abort();
  const events = [];
  for await (const event of provider.synthesize({ sessionId: "s1", language: "mixed", text: "Hello नमस्कार" }, controller.signal)) events.push(event);
  assert.deepEqual(events, [{ type: "synthesis_failed", error: { code: "interrupted", message: "Synthesis was cancelled.", retryable: true } }]);
});

test("teacher bridge follows playback state, requires viseme timing, and accepts board coordinates", () => {
  const audio = { url: "mock://reply.wav", contentType: "audio/wav" };
  assert.deepEqual(contract.teacherActionsForVoiceEvent({ type: "playback_started", audio }), [{ type: "teacher_state", state: "explain" }]);
  const synchronized = contract.teacherActionsForVoiceEvent({ type: "playback_started", audio: { ...audio, visemes: [{ atMs: 0, durationMs: 100, viseme: "aa" }] } });
  assert.deepEqual(synchronized.map(command => command.type), ["teacher_state", "teacher_action"]);
  assert.deepEqual(contract.teacherActionsForVoiceEvent({ type: "playback_interrupted" }), [{ type: "teacher_state", state: "idle" }]);
  assert.equal(contract.teacherActionsForVoiceEvent(contract.normalizedBoardCommand({ x: 0.25, y: 0.75 }))[0].action.target.x, 0.25);
  assert.throws(() => contract.normalizedBoardCommand({ x: 2, y: 0 }), /normalized/);
});
