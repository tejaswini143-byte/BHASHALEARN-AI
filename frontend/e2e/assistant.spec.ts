import { expect, test, type Page } from "@playwright/test";

async function mockAssistant(page: Page) {
  const deadlines: Array<Record<string, unknown>> = [];
  const settings = { modes: ["student"], timezone: "Asia/Kolkata", preferred_language: "te", reminder_phone: null, phone_verified: false, call_consent: false, reminder_lead_minutes: [1440, 60], quiet_start: null, quiet_end: null, enabled_integrations: [], email_policy: "draft_only", notifications: { email: true, call: false }, retention_days: 90, paused: false };
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "assistant-e2e-token"));
  await page.route("**/api/v1/assistant/**", async route => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname;
    expect(request.headers().authorization).toBe("Bearer assistant-e2e-token");
    if (path.endsWith("/settings") && request.method() === "GET") return route.fulfill({ json: settings });
    if (path.endsWith("/settings") && request.method() === "PATCH") return route.fulfill({ json: { ...settings, ...request.postDataJSON() } });
    if (path.endsWith("/deadlines") && request.method() === "GET") return route.fulfill({ json: deadlines });
    if (path.endsWith("/deadlines") && request.method() === "POST") { const item = { id: "deadline-1", ...request.postDataJSON(), status: "upcoming", priority: "normal", source: "manual" }; deadlines.unshift(item); return route.fulfill({ status: 201, json: item }); }
    if (path.endsWith("/drafts")) return route.fulfill({ json: [] });
    if (path.endsWith("/integrations")) return route.fulfill({ json: [{ provider: "gmail", status: "disconnected", available: false, message: "OAuth provider is not configured", account_email: null }, { provider: "calendar", status: "disconnected", available: false, message: "OAuth provider is not configured", account_email: null }] });
    return route.fulfill({ json: [] });
  });
}

test("assistant dashboard explains disconnected providers and schedules a manual deadline", async ({ page }) => {
  await mockAssistant(page);
  await page.goto("/assistant");
  await expect(page.getByRole("heading", { name: "Your personal assistant" })).toBeVisible();
  await expect(page.getByText(/Each provider requires separate OAuth consent/)).toBeVisible();
  await page.getByLabel("Title", { exact: true }).fill("Chemistry assignment");
  await page.getByLabel("Due date and time").fill("2032-04-05T14:30");
  await page.getByRole("button", { name: "Add deadline" }).click();
  await expect(page.getByText("Chemistry assignment")).toBeVisible();
  await expect(page.getByRole("status")).toContainText(/Deadline saved/);
  await expect(page.getByText(/Otherwise reminders are mock/)).toBeVisible();
});
