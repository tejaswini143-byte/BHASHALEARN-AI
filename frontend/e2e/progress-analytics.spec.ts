import { expect, test } from "@playwright/test";

const dashboardData = {
  range_days: 7, timezone: "UTC", date_rule: "UTC calendar days",
  overview: { learning_sessions: 4, completed_activities: 6, completed_assessments: 5, learning_time_minutes: null, learning_time_status: "not_recorded" },
  range_totals: { sessions: 2, completed_assessments: 3, mission_completions: 1 },
  trend: Array.from({ length: 7 }, (_, index) => ({
    date: "2026-11-" + String(index + 2).padStart(2, "0"), sessions: index === 5 ? 1 : 0,
    completed_assessments: index === 5 ? 2 : 0, mission_completions: index === 6 ? 1 : 0,
    activity_count: index === 5 ? 3 : index === 6 ? 1 : 0,
  })),
  topics: [{ topic: "Equivalent Fractions", subject: "Mathematics", mastery_score: 75, scored_attempts: 4, correct_attempts: 3 }],
  subjects: [{ subject: "Mathematics", mastery_score: 75, scored_attempts: 4 }],
  strengths: [{ topic: "Equivalent Fractions", mastery_score: 90, scored_attempts: 5 }],
  improvement_areas: [{ topic: "Equivalent Fractions", mastery_score: 75, scored_attempts: 4 }],
  mission: { xp: 135, level: 2, xp_into_level: 35, xp_to_next_level: 65, completed_missions: 2, badges: ["First Steps"] },
  streak: { days: 2, as_of_utc_date: "2026-11-08", timezone: "UTC", lower_bound: false },
  recent_activity: [{ kind: "assessment", title: "Practiced Equivalent Fractions", occurred_at: "2026-11-08T09:00:00Z", detail: "Correct" }],
  recommendations: [{ topic: "Equivalent Fractions", recommendation: "Review the prerequisite step.", reason: "Recorded accuracy is between 50% and 79%." }],
  quiz_analytics: { available: false, integration: "Future adapter" },
};

async function authenticateLocally(page) {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "mock-student-token"));
}

test("analytics renders real-shaped mocked data, supports range changes, and remains accessible on mobile", async ({ page }) => {
  await authenticateLocally(page);
  const requestedRanges: string[] = [];
  let releaseResponse = () => {};
  const routeGate = new Promise<void>(resolve => { releaseResponse = resolve; });
  await page.route("**/api/v1/analytics?range_days=*", async route => {
    const url = new URL(route.request().url());
    const days = Number(url.searchParams.get("range_days"));
    requestedRanges.push(String(days));
    await routeGate;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...dashboardData, range_days: days, trend: dashboardData.trend.slice(0, days) }) });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/progress-analytics");
  await expect(page.getByRole("status")).toContainText("Loading your recorded learning progress");
  releaseResponse();
  await expect(page.getByRole("heading", { name: "Your progress, in focus." })).toBeVisible();
  await expect(page.getByText("LIVE ACCOUNT DATA")).toBeVisible();
  await expect(page.getByText("Not recorded", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /Recorded learning activity across/ })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Mathematics mastery" })).toHaveAttribute("aria-valuenow", "75");
  await expect(page.getByText("Practiced Equivalent Fractions", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "30 days" }).click();
  await expect(page.getByRole("button", { name: "30 days" })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => requestedRanges).toContain("30");
  const dimensions = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
  for (const name of ["Dashboard", "Memories", "Voice Tutor", "Immersive Classroom", "Future Me", "Mission Mode"]) {
    await expect(page.getByRole("navigation", { name: "Learning navigation" }).getByRole("link", { name })).toBeVisible();
  }
});

test("new student empty state and offline state never display sample metrics", async ({ page }) => {
  await authenticateLocally(page);
  await page.route("**/api/v1/analytics?range_days=*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({
      ...dashboardData,
      overview: { learning_sessions: 0, completed_activities: 0, completed_assessments: 0, learning_time_minutes: null, learning_time_status: "not_recorded" },
      range_totals: { sessions: 0, completed_assessments: 0, mission_completions: 0 },
      trend: dashboardData.trend.map(item => ({ ...item, sessions: 0, completed_assessments: 0, mission_completions: 0, activity_count: 0 })),
      topics: [], subjects: [], strengths: [], improvement_areas: [],
      mission: { xp: 0, level: 1, xp_into_level: 0, xp_to_next_level: 100, completed_missions: 0, badges: [] },
      streak: { days: 0, as_of_utc_date: "2026-11-08", timezone: "UTC", lower_bound: false },
      recent_activity: [], recommendations: [{ topic: null, recommendation: "Start a short objective practice.", reason: "No scored answers yet." }],
    }),
  }));
  await page.goto("/progress-analytics");
  await expect(page.getByRole("heading", { name: "Your learning story starts here" })).toBeVisible();
  await expect(page.getByText("No badges recorded yet")).toBeVisible();
  await page.unrouteAll();
  await page.route("**/api/v1/analytics?range_days=*", route => route.abort("failed"));
  await page.getByRole("button", { name: "90 days" }).click();
  await expect(page.getByRole("heading", { name: "You’re offline" })).toBeVisible();
  await expect(page.getByText(/No sample student metrics/)).toBeVisible();
});

test("expired student analytics credentials are cleared and redirect to sign in", async ({ page }) => {
  await authenticateLocally(page);
  await page.route("**/api/v1/analytics?range_days=*", route => route.fulfill({
    status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid token" }),
  }));
  await page.goto("/progress-analytics");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Email address")).toBeVisible();
});
