import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

test("analytics route is authenticated, linked from dashboard, and uses only the bearer-owned API", async () => {
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
  const dashboard = await readFile(new URL("../src/Dashboard.tsx", import.meta.url), "utf8");
  const screen = await readFile(new URL("../src/ProgressAnalytics.tsx", import.meta.url), "utf8");
  assert.ok(app.includes('path="/progress-analytics"'));
  assert.ok(dashboard.includes('to="/progress-analytics"'));
  assert.ok(screen.includes("<Navigate to=\"/login\" replace />"));
  assert.ok(screen.includes('request<Analytics>("/analytics?range_days=" + range'));
  assert.ok(screen.includes('Authorization: "Bearer " + token'));
  assert.ok(!screen.includes("student_id"));
});

test("analytics UI states ranges, evidence labels, chart accessibility, and duration honestly", async () => {
  const screen = await readFile(new URL("../src/ProgressAnalytics.tsx", import.meta.url), "utf8");
  const styles = await readFile(new URL("../src/progress-analytics.css", import.meta.url), "utf8");
  for (const expected of [
    "Loading your recorded learning progress",
    "You’re offline",
    "No sample student metrics are being shown",
    "Your learning story starts here",
    "LIVE ACCOUNT DATA",
    "Recorded learning events only",
    "WEEKLY",
    "MONTHLY",
    "Subject mastery",
    "Learning timeline",
    "quiz_analytics",
    "role=\"img\"",
    "role=\"progressbar\"",
    "timeZone: \"UTC\"",
    "Session durations are not collected",
    "range === 7 ? \"WEEKLY\" : range === 30 ? \"MONTHLY\"",
  ]) assert.ok(screen.includes(expected), "missing analytics UI contract: " + expected);
  assert.ok(styles.includes("@media(max-width:680px)"));
  assert.ok(styles.includes("prefers-reduced-motion:reduce"));
});
