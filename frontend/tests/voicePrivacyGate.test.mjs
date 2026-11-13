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
  assert.match(source, /Interpret with Gemini/);
  assert.match(source, /Confirm and execute/);
});

test("microphone audio processing cannot auto-stop on a fixed RMS threshold", () => {
  const capture = source.slice(source.indexOf("processor.onaudioprocess ="), source.indexOf("source.connect(processor)"));
  assert.doesNotMatch(capture, /void finishRecording\(\)/);
  assert.doesNotMatch(capture, /await transcribeWav\(/);
  assert.match(source, /if \(elapsed >= 30\)/);
});
