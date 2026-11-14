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
  assert.match(panel, /http:\/\/127\.0\.0\.1:18771/);
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
  assert.match(panel, /currentPlanRef\.current = \{ id: planId, transcript: normalized, action: proposed \}/);
  assert.match(panel, /onClick=\{\(\) => void execute\(currentPlanRef\.current\?\.id\)\}/);
  assert.match(panel, /executionInProgressRef\.current = true/);
  assert.match(panel, /executionGateRef\.current\.begin\(planId\)/);
});

test("transcript review and Gemini planning only prepare a plan and never execute it", async () => {
  const panel = await read("../src/DesktopControlPanel.tsx");
  const interpret = panel.slice(panel.indexOf("async function interpret()"), panel.indexOf("function describe("));
  const review = panel.slice(panel.indexOf('>I reviewed this transcript</button>') - 800, panel.indexOf('>I reviewed this transcript</button>') + 40);
  assert.match(interpret, /assistant\/desktop\/interpret/);
  assert.match(interpret, /registerPlan\(planId\)/);
  assert.doesNotMatch(interpret, /\bexecute\s*\(/);
  assert.doesNotMatch(interpret, /\/desktop\/execute/);
  assert.match(review, /setReviewedTranscript\(/);
  assert.doesNotMatch(review, /execute\s*\(|\/desktop\/execute/);
});

test("only the confirmed plan handler requests a one-use companion execution ticket", async () => {
  const panel = await read("../src/DesktopControlPanel.tsx");
  const execute = panel.slice(panel.indexOf("async function execute("), panel.indexOf("async function stop("));
  assert.match(execute, /executionGateRef\.current\.begin\(planId\)/);
  assert.match(execute, /companion\("\/desktop\/confirm", executionPayload\)/);
  assert.match(execute, /companion\("\/desktop\/execute", \{ \.\.\.executionPayload, confirmation_token: confirmation\.confirmation_token \},/);
  assert.ok(execute.indexOf('companion("/desktop/confirm"') < execute.indexOf('companion("/desktop/execute"'));
  assert.match(execute, /executionInProgressRef\.current\) return/);
});

test("a plan requires one fresh confirmation and cannot be consumed twice", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const gate = createDesktopExecutionGate();
  gate.enable();
  assert.throws(() => gate.begin("plan-1"), /fresh confirmation/);
  gate.registerPlan("plan-1");
  const token = gate.begin("plan-1");
  assert.throws(() => gate.begin("plan-1"), /already executing/);
  gate.finish(token);
  assert.throws(() => gate.begin("plan-1"), /fresh confirmation/);
  gate.registerPlan("plan-2");
  assert.doesNotThrow(() => gate.begin("plan-2"));
});

test("a changed transcript invalidates its pending action approval", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const panel = await read("../src/DesktopControlPanel.tsx");
  const gate = createDesktopExecutionGate();
  gate.enable();
  gate.registerPlan("open-notepad-transcript-1");
  assert.match(panel, /useEffect\(\(\) => \{\s*executionGateRef\.current\.invalidatePlan\(\);\s*currentPlanRef\.current = null;\s*setReviewedTranscript\(""\);/);
  gate.invalidatePlan();
  assert.throws(() => gate.begin("open-notepad-transcript-1"), /fresh confirmation/);
});

test("disabled desktop control cannot start an approved plan", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const gate = createDesktopExecutionGate();
  assert.throws(() => gate.begin("plan-1"), /disabled/);
  gate.enable();
  gate.registerPlan("plan-1");
  gate.disable();
  assert.throws(() => gate.begin("plan-1"), /disabled/);
});

test("Emergency Stop cancels the remaining ordered desktop steps", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const gate = createDesktopExecutionGate();
  gate.enable();
  gate.registerPlan("pending-sequence");
  const token = gate.begin("pending-sequence");
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

test("a Prisma transcript must be explicitly reviewed before Gemini planning", async () => {
  const panel = await read("../src/DesktopControlPanel.tsx");
  assert.match(panel, /I reviewed this transcript/);
  assert.match(panel, /reviewedTranscript !== normalized/);
  assert.match(panel, /reviewedTranscript !== transcript\.normalize\("NFC"\)\.trim\(\)/);
  assert.doesNotMatch(panel, /Interpret each new Prisma transcript as a desktop command/);
});

test("target-independent app launches use a fresh snapshot without weakening target-bound checks", async () => {
  const panel = await read("../src/DesktopControlPanel.tsx");
  assert.match(panel, /function requiresBoundTargets\(step: Action\)/);
  assert.match(panel, /const needsBoundTargets = requiresBoundTargets\(approvedAction\)/);
  assert.match(panel, /needsBoundTargets \? snapshot\.snapshot_id : currentSnapshot\.snapshot_id/);
  assert.match(panel, /if \(needsBoundTargets && approvedAction\.action !== "type_qa_text" && !fillsDemoForm && \(currentSnapshot\.active_window_id/);
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

test("late Gemini plan is rejected after Emergency Stop and re-enable", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const gate = createDesktopExecutionGate();
  gate.enable();
  const requestEpoch = gate.snapshot();
  gate.disable();
  assert.equal(gate.isCurrent(requestEpoch), false);
  gate.enable();
  assert.equal(gate.isCurrent(requestEpoch), false, "Re-enabling must not revive stale Gemini responses");
  assert.throws(() => gate.begin("stale-plan"), /fresh confirmation/);
});

test("Emergency Stop invalidates an executing token even after re-enable", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const gate = createDesktopExecutionGate();
  gate.enable();
  gate.registerPlan("approved-sequence");
  const token = gate.begin("approved-sequence");
  gate.disable();
  gate.enable();
  assert.throws(() => gate.assertCurrent(token), /Emergency Stop cancelled/);
  assert.equal(gate.isCurrent(token), false);
  gate.finish(token);
  gate.registerPlan("fresh-sequence");
  const freshToken = gate.begin("fresh-sequence");
  assert.doesNotThrow(() => gate.assertCurrent(freshToken));
  gate.finish(freshToken);
});

test("plan invalidation prevents a pending approval from executing", async () => {
  const { createDesktopExecutionGate } = await import("../src/desktopExecution.mjs");
  const gate = createDesktopExecutionGate();
  gate.enable();
  gate.registerPlan("transcript-before-edit");
  const oldEpoch = gate.snapshot();
  gate.invalidatePlan();
  assert.equal(gate.isCurrent(oldEpoch), false);
  assert.throws(() => gate.begin("transcript-before-edit"), /fresh confirmation/);
});
