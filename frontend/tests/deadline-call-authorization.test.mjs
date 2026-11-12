import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ui = readFileSync(new URL("../src/DeadlineCallAssistant.tsx", import.meta.url), "utf8");
const companion = readFileSync(new URL("../../scripts/desktop_companion.py", import.meta.url), "utf8");

test("call answer and microphone require distinct trusted UI actions", () => {
  assert.match(ui, /event\.nativeEvent\.isTrusted\) void answer\(\)/);
  assert.match(ui, /event\.nativeEvent\.isTrusted\) void \(recording \? stopListening\(\) : startListening\(\)\)/);
  assert.match(ui, /initiating_component: "browser_answer_button"/);
  assert.match(ui, /initiating_component: "browser_microphone_button"/);
  assert.match(ui, /\/assistant\/local-calls\/" \+ encodeURIComponent\(callId\) \+ "\/transcribe"/);
});

test("companion polling and window creation do not answer or capture audio", () => {
  const poll = companion.slice(companion.indexOf("def _background_poll"), companion.indexOf("def _call_ui_mainloop"));
  const createWindow = companion.slice(companion.indexOf("def _show_incoming_call"), companion.indexOf("def _background_poll"));
  const windowInitialization = createWindow.slice(0, createWindow.indexOf("def begin_answer"));
  assert.doesNotMatch(poll, /_answer_call|_capture_wav|_begin_voice_turn/);
  assert.doesNotMatch(windowInitialization, /_answer_call|_capture_wav|_begin_voice_turn/);
  assert.match(createWindow, /answer\.configure\(command=begin_answer\)/);
  assert.match(companion, /initiating_component": "windows_answer_button"/);
  assert.match(companion, /"\/microphone"/);
  assert.match(companion, /"\/assistant\/local-calls\/" \+ call_id \+ "\/transcribe"/);
});
