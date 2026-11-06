import { test, expect } from "@playwright/test";
import { allowAuthenticatedTests, requireDedicatedLogin, signIn, testEmail, testPassword } from "./helpers";

test("Vite API proxy reaches the configured backend and preserves unauthenticated 401", async ({ request }) => {
  const backendUrl = process.env.BHASHALEARN_E2E_BACKEND_URL
    || (process.env.BHASHALEARN_E2E_START_SERVERS === "1" ? "http://127.0.0.1:8012" : "http://127.0.0.1:8002");
  const directHealth = await request.get(`${backendUrl}/health`);
  expect(directHealth.status()).toBe(200);
  const health = await request.get("/health");
  expect(health.status()).toBe(200);
  const protectedResponse = await request.get("/api/v1/documents");
  expect(protectedResponse.status()).toBe(401);
});

test("dashboard access redirects when no authenticated session exists", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});

test("dedicated student dashboard, navigation, documents route, and refresh work", async ({ page }) => {
  test.skip(!allowAuthenticatedTests || !requireDedicatedLogin(), "Set explicit dedicated E2E student credentials and allow authenticated reads.");
  const pageErrors: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  const failedApiRequests: string[] = [];
  page.on("requestfailed", request => { if (request.url().includes("/api/")) failedApiRequests.push(new URL(request.url()).pathname); });
  await signIn(page, testEmail, testPassword);
  await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Dashboard navigation" })).toBeVisible();
  await page.getByRole("link", { name: /documents/i }).first().click();
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  expect(pageErrors).toEqual([]);
  expect(failedApiRequests).toEqual([]);
});
