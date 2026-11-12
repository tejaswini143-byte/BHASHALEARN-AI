import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = path => readFile(new URL(path, import.meta.url), "utf8");

test("desktop commands use the approved QA page and semantic targets only", async () => {
  const helper = await read("../src/desktopDomTargets.ts");
  const panel = await read("../src/DesktopControlPanel.tsx");
  assert.match(helper, /APPROVED_HOSTS/);
  assert.match(helper, /APPROVED_PORTS/);
  assert.match(helper, /"5202"/);
  assert.match(helper, /"5203"/);
  assert.match(helper, /desktop-control-test\.html/);
  assert.match(helper, /catch \{\s*\/\/ Cross-origin documents are never inspected or controlled/);
  assert.match(helper, /data-desktop-target/);
  assert.match(helper, /PLACEHOLDERS and values are intentionally excluded/i);
  assert.match(panel, /body: JSON\.stringify\(\{ transcript: normalized, targets, approved_sites \}\)/);
  assert.match(panel, /companion\("\/desktop\/snapshot"\)/);
  assert.match(panel, /snapshot\.active_window_id/);
  assert.match(panel, /Confirm and execute/);
  assert.match(panel, /currentSnapshot\.active_window_id !== snapshot\.active_window_id/);
  assert.match(panel, /currentSnapshot\.focused_target_id !== snapshot\.focused_target_id/);
  assert.match(panel, /Emergency Stop/);
  assert.match(panel, /bindNamedClickTargets/);
  assert.match(panel, /blocked the unbound click/);
  assert.match(panel, /different element than the one you named/);
  assert.match(panel, /allowedCompanionBases = new Set\(\[[^\]]*"http:\/\/127\.0\.0\.1:18770"/);
  assert.match(panel, /companion\("\/action", \{ action: "move_to", \.\.\.point \}\);\s*assertExecutionActive\(executionEpoch\);\s*await wait\(280\)/);
  assert.match(panel, /executionGateRef\.current\.assertCurrent\(executionEpoch\)/);
  assert.match(panel, /executionGateRef\.current\.disable\(\)/);
});

test("Emergency Stop cancels the remaining ordered desktop steps", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const gate = createDesktopExecutionGate();
  gate.enable();
  const token = gate.begin();
  const completed = [];
  let release;
  const pendingAction = new Promise(resolve => { release = resolve; });
  const workflow = (async () => {
    gate.assertCurrent(token);
    completed.push("move");
    await pendingAction;
    gate.assertCurrent(token);
    completed.push("click");
  })();
  gate.disable();
  release();
  await assert.rejects(workflow, /Emergency Stop cancelled/);
  assert.deepEqual(completed, ["move"]);
  assert.equal(gate.isCurrent(token), false);
});

test("disposable QA provides uniquely named, duplicate, search, typing, and sandbox targets", async () => {
  const page = await read("../public/desktop-control-test.html");
  const sandbox = await read("../public/desktop-control-sandbox.html");
  assert.match(page, /data-desktop-target="qa-login-button"/);
  assert.match(page, /data-desktop-target="qa-visual-button"/);
  assert.match(page, /data-desktop-target="qa-search-field"/);
  assert.match(page, /data-desktop-target="qa-permitted-field"/);
  assert.match(page, /QA-only click target; it does not open a sign-in page or authenticate anyone/);
  assert.match(page, /id="qa-navigation-link"[^>]+href="\/desktop-control-sandbox\.html"[^>]+onclick=/);
  assert.equal((page.match(/data-desktop-target="qa-chapter-/g) || []).length, 2);
  assert.match(page, /id="approved-site-frame"/);
  assert.match(sandbox, /sandbox-lesson-button/);
  assert.match(sandbox, /desktopQa:true/);
  assert.match(sandbox, /Click event fired; approved destination loaded:/);
});
