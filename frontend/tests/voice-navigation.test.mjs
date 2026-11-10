import test from "node:test";
import assert from "node:assert/strict";
import { matchVoiceNavigationCommand } from "../src/voiceNavigation.mjs";

test("voice navigation accepts exact English and Telugu allowlisted commands", () => {
  assert.deepEqual(matchVoiceNavigationCommand("Open dashboard!"), { label: "Dashboard", path: "/dashboard" });
  assert.deepEqual(matchVoiceNavigationCommand("నా పురోగతి చూపించు"), { label: "My Progress", path: "/progress-analytics" });
  assert.deepEqual(matchVoiceNavigationCommand("Start AI Classroom"), { label: "AI Classroom", path: "/classroom" });
  assert.deepEqual(matchVoiceNavigationCommand("go to future advisor"), { label: "Career Advisor", path: "/career" });
  assert.deepEqual(matchVoiceNavigationCommand("open my uploaded PDF"), { label: "My Documents", path: "/documents" });
  assert.deepEqual(matchVoiceNavigationCommand("go back"), { label: "Previous page", path: "__back__" });
});

test("voice navigation rejects conversation and ambiguous commands", () => {
  assert.equal(matchVoiceNavigationCommand("Can you open the dashboard and explain fractions?"), null);
  assert.equal(matchVoiceNavigationCommand("open my email"), null);
  assert.equal(matchVoiceNavigationCommand(""), null);
});
