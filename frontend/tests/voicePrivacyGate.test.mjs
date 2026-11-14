import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Source-level guardrails complement (not replace) browser microphone acceptance tests.
const source = readFileSync(new URL("../src/VoiceTutor.tsx", import.meta.url), "utf8");

test("recording completion requires local review rather than automatic upload", () => {
  const finish = source.slice(source.indexOf("async function finishRecording()"), source.indexOf("async function toggleRecording()"));
  assert.ok(finish.includes("setPendingCapture(blob)"), "Completed audio must enter local review");
  assert.ok(finish.includes("URL.createObjectURL(blob)"), "Completed audio must have local playback");
  assert.ok(!finish.includes("await transcribeWav("), "Recording stop must never auto-submit audio");
});

test("Prisma submission is user-triggered and explicitly labeled", () => {
  const submit = source.slice(source.indexOf("async function submitPendingCapture()"), source.indexOf("async function transcribeWav("));
  assert.match(submit, /await transcribeWav\(blob\)/);
  assert.match(source, /onClick=\{\(\) => void submitPendingCapture\(\)\}/);
  assert.match(source, /Send reviewed recording to Prisma/);
  assert.match(source, /Discard recording/);
});

test("microphone capture requires explicit browser user interaction", () => {
  assert.match(source, /onClick=\{\(\) => void toggleRecording\(\)\}/);
  assert.match(source, /navigator\.mediaDevices\.getUserMedia/);
  assert.match(source, /deviceId: \{ exact: microphoneDeviceId \}/);
  assert.match(source, /audio controls src=\{capturePreviewUrl\}/);
});

test("failed Prisma transcription retains the reviewed audio for retry or discard", () => {
  const submit = source.slice(source.indexOf("async function submitPendingCapture()"), source.indexOf("async function transcribeWav("));
  assert.match(submit, /const recognized = await transcribeWav\(blob\)/);
  assert.match(submit, /if \(recognized\) discardPendingCapture\(\)/);
  assert.match(source, /catch \(cause\) \{ if \(!controller\.signal\.aborted\) handleError\(cause\); return false; \}/);
});

test("Windows control remains gated by separate transcript review, Gemini plan and action confirmation", () => {
  assert.match(source, /I reviewed this transcript/);
  assert.match(source, /then prepare an action, review the proposal/);
  assert.match(source, /Confirm and execute/);
});

test("microphone audio processing cannot auto-stop on a fixed RMS threshold", () => {
  const capture = source.slice(source.indexOf("processor.onaudioprocess ="), source.indexOf("source.connect(processor)"));
  assert.doesNotMatch(capture, /void finishRecording\(\)/);
  assert.doesNotMatch(capture, /await transcribeWav\(/);
  assert.match(source, /if \(elapsed >= 30\)/);
});

test("a new microphone recording invalidates the previous command transcript", () => {
  const start = source.slice(source.indexOf("async function toggleRecording()"), source.indexOf("function generateLocalDemo("));
  assert.match(start, /setDraft\(""\)/);
});

test("pending microphone recording pins the session and language until review", () => {
  assert.match(source, /aria-label="Voice learning session"[^>]*Boolean\(pendingCapture\)/);
  assert.match(source, /<select value=\{language\}[^>]*Boolean\(pendingCapture\)/);
  assert.match(source, /Send or discard the reviewed recording before changing its language/);
});


test("unavailable recording does not discard an existing reviewed capture", () => {
  const start = source.slice(source.indexOf("async function toggleRecording()"), source.indexOf("function generateLocalDemo("));
  const guards = start.indexOf("if (!selected || creating || busy || transcribing || voiceTurnActive.current || micRequestActive.current) return;");
  const discard = start.indexOf("discardPendingCapture();");
  assert.ok(guards >= 0 && discard > guards, "Invalid recording attempts must preserve reviewed audio");
  assert.ok(start.indexOf("setDraft(\"\");") > guards, "Invalid recording attempts must preserve the previous transcript");
});

test("microphone activation is not triggered by page effects", () => {
  const capture = source.slice(source.indexOf("async function toggleRecording()"), source.indexOf("function generateLocalDemo("));
  assert.match(capture, /navigator\.mediaDevices\.getUserMedia/);
  const outsideCapture = source.replace(capture, "");
  assert.doesNotMatch(outsideCapture, /navigator\.mediaDevices\.getUserMedia\(/);
});


test("microphone capture requires a second explicit decision before getUserMedia", () => {
  const start = source.slice(source.indexOf("async function toggleRecording()"), source.indexOf("function generateLocalDemo("));
  const consent = start.indexOf('window.confirm("BHASHALEARN AI will start recording your microphone locally. Start recording?")');
  const capture = start.indexOf("navigator.mediaDevices.getUserMedia({");
  assert.ok(start.indexOf("discardPendingCapture();") > capture, "Preserve the previous preview until microphone startup succeeds");
  assert.ok(consent >= 0 && capture > consent, "Microphone capture must be preceded by a separate user confirmation");
  assert.match(start, /if \(!window\.confirm\([\s\S]*?\)\) return;/);
});


test("unmount during asynchronous audio startup releases microphone tracks", () => {
  const start = source.slice(source.indexOf("async function toggleRecording()"), source.indexOf("function generateLocalDemo("));
  assert.match(start, /await context\.resume\(\);\s*\/\/[^\n]*\n\s*\/\/[^\n]*\n\s*if \(!mounted\.current\) \{ await releaseMicrophone\(\); return; \}/);
});


test("late Gemini failures cannot overwrite Emergency Stop status", () => {
  const panel = readFileSync(new URL("../src/DesktopControlPanel.tsx", import.meta.url), "utf8");
  const interpret = panel.slice(panel.indexOf("  async function interpret()"), panel.indexOf("  function describe("));
  assert.match(interpret, /catch \(error\) \{\s*\/\/[^\n]*\n\s*if \(activeRef\.current && executionGateRef\.current\.isCurrent\(requestEpoch\)\)/);
});
