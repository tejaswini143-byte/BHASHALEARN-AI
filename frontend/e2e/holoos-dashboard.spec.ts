import { expect, test, type Page } from "@playwright/test";

const date = "2026-11-01T10:00:00Z";
const progress = [{ id: "p-1", topic: "Fractions", mastery_score: 76, attempts: 2, evidence_attempts: 2, evidence_status: "assessed", correct_attempts: 2, incorrect_attempts: 0, recommendation: "Keep practicing", updated_at: date }];
const initialSessions = [
  { id: "s-1", topic: "Telugu greetings", language: "Telugu", created_at: date },
  { id: "s-2", topic: "English fractions", language: "English", created_at: date },
];

async function mockDashboard(page: Page, failCreate = false) {
  const sessions = [...initialSessions];
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "holoos-browser-test-token"));
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    expect(request.headers().authorization).toBe("Bearer holoos-browser-test-token");
    if (url.pathname.endsWith("/auth/me")) {
      await route.fulfill({ json: { id: "student-1", email: "learner@example.test", display_name: "Test Learner" } }); return;
    }
    if (url.pathname.endsWith("/progress")) { await route.fulfill({ json: progress }); return; }
    if (url.pathname.endsWith("/sessions") && request.method() === "GET") { await route.fulfill({ json: sessions }); return; }
    if (url.pathname.endsWith("/students/me/preferences")) {
      await route.fulfill({ json: { preferred_language: "English", learning_level: "beginner", learning_goal: null } }); return;
    }
    if (url.pathname.endsWith("/sessions") && request.method() === "POST") {
      if (failCreate) { await route.fulfill({ status: 422, json: { detail: "That topic could not be saved. Try a shorter title." } }); return; }
      const created = { id: "s-3", ...request.postDataJSON(), created_at: date };
      sessions.unshift(created);
      await route.fulfill({ status: 201, json: created }); return;
    }
    await route.fulfill({ status: 404, json: { detail: "Not found" } });
  });
}

test("mobile dashboard navigation works with keyboard and closes on Escape", async ({ page }) => {
  await mockDashboard(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: /welcome back, test/i })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Fractions mastery" })).toHaveAttribute("aria-valuenow", "76");
  const menu = page.getByRole("button", { name: "Open dashboard navigation" });
  await menu.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".db-menu-toggle")).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("link", { name: /Immersive classroom/ })).toHaveAttribute("href", "/immersive");
  await expect(page.getByRole("link", { name: /Future Me/ })).toHaveAttribute("href", "/future-me");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Open dashboard navigation" })).toBeFocused();
  await expect(page.getByRole("link", { name: /Overview/ })).toBeHidden();
  await page.setViewportSize({ width: 320, height: 740 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("session search and create errors give clear, announced feedback", async ({ page }) => {
  await mockDashboard(page, true);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: /welcome back, test/i })).toBeVisible();
  await page.getByRole("textbox", { name: "Search sessions" }).fill("telugu");
  await expect(page.getByText("Telugu greetings")).toBeVisible();
  await expect(page.getByText("English fractions")).toHaveCount(0);
  await page.getByLabel("What would you like to learn?").fill("An extremely long topic");
  await page.getByRole("button", { name: /create learning session/i }).click();
  await expect(page.getByRole("alert")).toContainText("Try a shorter title");
});
