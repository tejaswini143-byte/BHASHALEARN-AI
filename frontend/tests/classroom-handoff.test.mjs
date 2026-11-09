import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const sourceDir = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const handoff = require(resolve(sourceDir, "classroomHandoff.ts"));
const tutor = require(resolve(sourceDir, "classroomTutor.ts"));

test("classroom invitation classifies educational questions and keeps ordinary chat in chat", () => {
  assert.equal(handoff.isEducationalDoubt("Why do fractions need a common denominator?"), true);
  assert.equal(handoff.isEducationalDoubt("తెలుగు అర్థం ఏమిటి"), true);
  assert.equal(handoff.isEducationalDoubt("Thanks!"), false);
});

test("teacher selection URL preserves session and the exact Unicode doubt", () => {
  const url = new URL(handoff.classroomUrl("session-123", "Explain గురుత్వాకర్షణ?", "holographic"), "https://local.invalid");
  assert.equal(url.searchParams.get("session"), "session-123");
  assert.equal(url.searchParams.get("question"), "Explain గురుత్వాకర్షణ?");
  assert.equal(url.searchParams.get("mode"), "holographic");
});

test("classroom tutor uses a deterministic transport mock with the original lesson context", async () => {
  let captured;
  const mockTransport = async (sessionId, message) => {
    captured = { sessionId, message };
    return { reply: "Mock explanation: divide both sides by the same value." };
  };
  const result = await tutor.generateClassroomExplanation({
    sessionId: "session-123", question: "Why does x + 3 = 8 give x = 5?", language: "telugu", learningLevel: "beginner",
  }, mockTransport);
  assert.equal(captured.sessionId, "session-123");
  assert.match(captured.message, /Why does x \+ 3 = 8 give x = 5\?/);
  assert.match(captured.message, /language=telugu, level=beginner/);
  assert.match(result.reply, /Mock explanation/);
  assert.throws(() => tutor.generateClassroomExplanation({ sessionId: "", question: "doubt", language: "english", learningLevel: "beginner" }, mockTransport), /required/);
});

test("chat invitation and classroom controls are wired without invoking paid providers in tests", async () => {
  const [chat, classroom] = await Promise.all([
    readFile(resolve(sourceDir, "AdvancedChat.tsx"), "utf8"),
    readFile(resolve(sourceDir, "TeacherPreview.tsx"), "utf8"),
  ]);
  assert.ok(chat.includes("Would you like me to explain this in our interactive classroom?"));
  assert.ok(chat.includes("Continue in chat"));
  assert.ok(chat.includes("Human Teacher"));
  assert.ok(chat.includes("Hologram Teacher"));
  assert.ok(classroom.includes("Start explanation"));
  assert.ok(classroom.includes("Pause / resume"));
  assert.ok(classroom.includes("Repeat"));
  assert.ok(classroom.includes("Stop"));
  assert.ok(classroom.includes("Ask another doubt"));
  assert.ok(classroom.includes("getSharedSessionContext(activeSessionId)"));
  assert.ok(classroom.includes("Approximate audio-timed mouth motion; no phoneme alignment"));
});
