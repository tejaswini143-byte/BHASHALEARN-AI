import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const student = { id: "screen-student", email: "student@example.test", display_name: "Meera Student" };
const preferences = { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: "Practice everyday English" };
const session = { id: "screen-session", topic: "House and rooms", language: "english", course_id: null, created_at: "2026-11-14T10:00:00Z" };
const settings = { modes: ["student"], timezone: "Asia/Calcutta", preferred_language: "mixed", max_call_duration_minutes: 30, reminder_phone: null, phone_verified: false, call_consent: false, reminder_lead_minutes: [60], quiet_start: null, quiet_end: null, enabled_integrations: [], email_policy: "draft_only", notifications: { email: true, call: false, desktop_call: false, save_call_transcripts: false }, retention_days: 90, paused: false };
const analytics = { range_days: 7, timezone: "Asia/Calcutta", recent_activity: [{ kind: "session", title: "House and rooms", detail: "Practice lesson", occurred_at: "2026-11-14T10:00:00Z" }], trend: [{ date: "2026-11-14", activity_count: 1, sessions: 1, completed_assessments: 0, mission_completions: 0 }], overview: { learning_sessions: 1, completed_activities: 0, completed_assessments: 0, learning_time_minutes: null, learning_time_status: "unavailable" }, range_totals: { sessions: 1, completed_assessments: 0, mission_completions: 0, completed_quizzes: 0 }, topics: [], subjects: [], strengths: [], improvement_areas: [], mission: { xp: 15, level: 1, xp_into_level: 15, xp_to_next_level: 85, completed_missions: 0, badges: [] }, streak: { days: 0, as_of_utc_date: "2026-11-14", timezone: "Asia/Calcutta", lower_bound: false }, recommendations: [], quiz_analytics: { available: false, completed_quizzes: 0, completed_questions: 0, average_score: null, integration: "unavailable" } };

async function installApi(page: Page, options: { onSchedule?: (body: Record<string, unknown>) => void; onLocalCall?: () => void } = {}) {
  let deadlines: Record<string, unknown>[] = [{ id: "practice-1", title: "Everyday English", due_at: "2026-12-01T10:00:00Z", timezone_name: "Asia/Calcutta", priority: "normal", category: "practice_call", status: "upcoming", source: "student" }];
  let localCalls: Record<string, unknown>[] = [];
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/students/me" || path === "/auth/me") return route.fulfill({ json: student });
    if (path === "/students/me/preferences") return route.fulfill({ json: preferences });
    if (path === "/progress") return route.fulfill({ json: [] });
    if (path === "/missions") return route.fulfill({ json: { missions: [], xp: 15, level: 1, xp_into_level: 15, xp_to_next_level: 85, badges: [] } });
    if (path.startsWith("/courses/catalog")) return route.fulfill({ json: [{ id: "telugu-basics", title: "Telugu Basics", description: "Start learning Telugu.", provider: "in_app", content_type: "in_app", language: "telugu", level: "beginner", estimated_minutes: 45, prerequisites: [], skills: [], lessons: [], lessons_count: 4, lessons_completed: 1, progress_percent: 25, completed: false, enrolled: true, completed_lesson_ids: [], next_lesson_id: null, enrolled_at: "2026-11-01T00:00:00Z" }] });
    if (path === "/analytics") return route.fulfill({ json: analytics });
    if (path === "/sessions" && method === "GET") return route.fulfill({ json: [session] });
    if (path === "/documents" && method === "GET") return route.fulfill({ json: [] });
    if (path === "/sessions" && method === "POST") return route.fulfill({ status: 201, json: session });
    if (path.endsWith("/context")) return route.fulfill({ json: { session_id: session.id, topic: session.topic, preferred_language: "english", learning_level: "beginner", learning_pace: "steady", learning_goal: preferences.learning_goal, messages: [], visual_lesson: null } });
    if (path.includes("/visual-context")) return route.fulfill({ json: {} });
    if (path === "/visual-lessons/session-state" || path.startsWith("/visual-lessons/session-state?")) return route.fulfill({ json: { state: null } });
    if (path === "/visual-lessons") return route.fulfill({ json: [] });
    if (path === "/assistant/settings") return route.fulfill({ json: settings });
    if (path === "/assistant/deadlines" && method === "GET") return route.fulfill({ json: deadlines });
    if (path === "/assistant/deadlines" && method === "POST") {
      const body = request.postDataJSON() as Record<string, unknown>; options.onSchedule?.(body);
      const created = { ...body, id: `practice-${deadlines.length + 1}`, timezone_name: body.timezone ?? "Asia/Calcutta", status: "upcoming", source: "student" };
      deadlines = [...deadlines, created]; return route.fulfill({ status: 201, json: created });
    }
    if (path.startsWith("/assistant/deadlines/") && path.endsWith("/cancel")) return route.fulfill({ json: { status: "canceled" } });
    if (path === "/assistant/local-calls" || path === "/assistant/local-calls/pending") return route.fulfill({ json: localCalls });
    if (path === "/assistant/local-calls/test" && method === "POST") {
      options.onLocalCall?.(); const call = { id: "local-call-1", deadline_id: null, title: "Bilingual practice", status: "ringing", language: "mixed", max_duration_minutes: 30, created_at: new Date().toISOString() };
      localCalls = [call]; return route.fulfill({ status: 201, json: call });
    }
    if (path.endsWith("/snooze") || path.endsWith("/dismiss")) return route.fulfill({ json: { id: "local-call-1", status: path.endsWith("/snooze") ? "snoozed" : "dismissed", created_at: new Date().toISOString() } });
    if (["/assistant/drafts", "/assistant/integrations", "/assistant/emails", "/assistant/calls", "/assistant/activity", "/assistant/calendar/events", "/assistant/livekit-sessions"].includes(path)) return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });
}

test("house picture lesson supports navigation, vocabulary selection, quiz, and bilingual copy", async ({ page }) => {
  await installApi(page);
  await page.goto("/"); await page.evaluate(() => sessionStorage.setItem("bhashalearn_access_token", "screen-fixture-token"));
  await page.goto("/visual-lessons");
  await expect(page.getByRole("heading", { name: "Learn words around the house" })).toBeVisible();
  await expect(page.getByRole("img", { name: "A house in a green garden" })).toBeVisible();
  await page.getByRole("button", { name: "tree", exact: true }).click();
  await expect(page.getByText("Step 1: Learn the word")).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Which room do we sleep in?")).toBeVisible();
  await page.getByLabel("Bedroom").check(); await page.getByRole("button", { name: "Check answer" }).click();
  await expect(page.getByRole("status")).toContainText("Correct!");
  await page.getByLabel("Explanation language").selectOption("te");
  await expect(page.getByRole("heading", { name: "ఇంటి చుట్టూ పదాలు నేర్చుకోండి" })).toBeVisible();
});

test("practice scheduler writes the existing deadline contract and shows the new session", async ({ page }) => {
  let scheduled: Record<string, unknown> | undefined;
  await installApi(page, { onSchedule: body => { scheduled = body; } });
  await page.goto("/"); await page.evaluate(() => sessionStorage.setItem("bhashalearn_access_token", "screen-fixture-token"));
  await page.goto("/assistant");
  await expect(page.getByRole("heading", { name: "Schedule a Practice Call", exact: true })).toBeVisible();
  await page.locator("#schedule-practice-call").getByLabel("Date and time").fill("2027-01-20T11:30");
  await page.getByRole("button", { name: "Schedule Practice Call" }).click();
  await expect(page.getByText("Practice reminder scheduled", { exact: false })).toBeVisible();
  expect(scheduled).toMatchObject({ title: "English speaking practice", category: "practice_call", priority: "normal" });
  await expect(page.locator(".as-upcoming-card").getByText("English speaking practice")).toBeVisible();
  await page.getByRole("link", { name: /Call Now/ }).click();
  await expect(page).toHaveURL(/#browser-practice-call$/);
});

test("incoming browser practice call appears as an accessible prompt and can be snoozed", async ({ page }) => {
  let started = false;
  await installApi(page, { onLocalCall: () => { started = true; } });
  await page.goto("/"); await page.evaluate(() => sessionStorage.setItem("bhashalearn_access_token", "screen-fixture-token"));
  await page.goto("/assistant");
  await page.getByText("Open call controls and incoming-call options").click();
  await page.getByRole("button", { name: "Start local Test Call" }).click();
  const dialog = page.getByRole("dialog", { name: "Incoming BHASHALEARN practice call" });
  await expect(dialog).toBeVisible(); await expect(dialog.getByRole("button", { name: "Answer" })).toBeFocused();
  expect(started).toBe(true);
  await dialog.getByRole("button", { name: "Snooze 10 min" }).click();
  await expect(dialog).not.toBeVisible();
});

test("social sign-in controls clearly identify the safe demo state", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /Google Demo/ }).click();
  await expect(page.getByRole("status")).toContainText("did not sign you in");
  await expect(page).toHaveURL(/\/login$/);
});

test("capture all 15 reference screens at desktop and mobile sizes", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  await installApi(page);
  const output = resolve("..", "docs", "design-reference", "captures"); mkdirSync(output, { recursive: true });
  const screens = [
    ["01-login", "/login", false], ["02-register", "/register", false], ["03-forgot-password", "/forgot-password", false],
    ["04-dashboard", "/dashboard", true], ["05-ai-classroom", "/voice", true], ["06-ai-chatbot", "/chat", true],
    ["07-pdf-learning-studio", "/documents", true], ["08-my-courses", "/courses", true], ["09-learning-timeline", "/timeline", true],
    ["10-progress-analytics", "/progress-analytics", true], ["11-settings", "/settings", true], ["12-mobile-dashboard", "/dashboard", true],
    ["13-visual-lesson-studio", "/visual-lessons", true], ["14-certificate", "/certificate", true], ["15-call-scheduler", "/assistant", true],
  ] as const;
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(`${new URL(page.url()).pathname}: ${error.message}`));
  for (const [name, path, authenticated] of screens) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.evaluate(value => value ? sessionStorage.setItem("bhashalearn_access_token", "screen-fixture-token") : sessionStorage.removeItem("bhashalearn_access_token"), authenticated);
    await page.goto(path, { waitUntil: "domcontentloaded" });
    if (name === "13-visual-lesson-studio") await expect(page.getByRole("heading", { name: "Learn words around the house" })).toBeVisible();
    if (name === "15-call-scheduler") await expect(page.getByRole("heading", { name: "Schedule a Practice Call", exact: true })).toBeVisible();
    await page.screenshot({ path: resolve(output, `${name}-desktop.png`), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    // Responsive sidebars animate out when the viewport crosses their breakpoint.
    // Wait for that transition before capturing so the mobile evidence reflects
    // the closed-menu default instead of a transient frame from the animation.
    await page.waitForTimeout(300);
    const mobileWidth = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      overflowing: [...document.querySelectorAll<HTMLElement>("body *")]
        .map(element => ({ name: element.tagName.toLowerCase() + (element.className ? `.${String(element.className).trim().replace(/\s+/g, ".")}` : ""), right: Math.round(element.getBoundingClientRect().right) }))
        .filter(element => element.right > window.innerWidth + 2)
        .slice(0, 5),
    }));
    expect(mobileWidth.document, `${name} mobile horizontal overflow: ${JSON.stringify(mobileWidth.overflowing)}`).toBeLessThanOrEqual(mobileWidth.viewport);
    await page.screenshot({ path: resolve(output, `${name}-mobile.png`), fullPage: true });
  }
  expect(errors, `${testInfo.title} browser errors`).toEqual([]);
});
