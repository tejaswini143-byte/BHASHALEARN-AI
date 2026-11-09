import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

test("assistant keeps email sending behind a separate confirmation after approval", async () => {
  const component = await readFile(new URL("../src/AssistantDashboard.tsx", import.meta.url), "utf8");
  assert.match(component, /Sending remains a separate action/);
  assert.match(component, /Send this approved email now\?/);
  assert.match(component, /Idempotency-Key/);
  assert.match(component, /Reply draft created; it has not been sent/);
  assert.match(component, /Pause all automation/);
});

test("research and assistant task actions have explicit approval states", async () => {
  const component = await readFile(new URL("../src/ResearchWorkspace.tsx", import.meta.url), "utf8");
  assert.match(component, /request-approval/);
  assert.match(component, /approve/);
  assert.match(component, /cancel/);
  assert.match(component, /Browser execution and external actions are unavailable/);
});
