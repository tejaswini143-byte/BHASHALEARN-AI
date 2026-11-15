import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("real HTTP student journey preserves the session when Gemini is unavailable", async ({ page }) => {
  const studentEmail = `rc-student-${Date.now()}@example.com`;
  const password = `Synthetic-${randomUUID()}-e2e!`;
  const apiStatuses: Array<{ path: string; status: number }> = [];
  const liveAiProviderRequests: string[] = [];
  const browserConsoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedAssetOrigins: string[] = [];
  const failedResponses: string[] = [];

  page.on("request", request => {
    const host = new URL(request.url()).hostname.toLowerCase();
    if (host === "generativelanguage.googleapis.com" || host.endsWith(".gnani.ai")) liveAiProviderRequests.push(host);
  });
  page.on("response", response => {
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/v1/")) apiStatuses.push({ path: url.pathname, status: response.status() });
    if (response.status() >= 400) failedResponses.push(`${response.status()} ${url.pathname}`);
  });
  page.on("console", message => {
    if (message.type() === "error") browserConsoleErrors.push(`${message.text()} @ ${JSON.stringify(message.location())}`);
  });
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("requestfailed", request => {
    const url = new URL(request.url());
    failedAssetOrigins.push(url.hostname.toLowerCase());
  });

  await page.goto("/register");
  await page.getByLabel("Your name").fill("RC Synthetic Student");
  await page.getByLabel("Email address").fill(studentEmail);
  await page.locator('input[autocomplete="new-password"]').fill(password);
  await page.getByRole("button", { name: /Create account/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: /Good to see you/ })).toBeVisible();

  await page.getByRole("button", { name: /Sign out/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email address").fill(studentEmail);
  await page.locator('input[autocomplete="current-password"]').fill(password);
  await page.getByRole("button", { name: /Sign in/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: /Good to see you/ })).toBeVisible();

  await page.getByRole("link", { name: /Start learning/ }).click();
  await expect(page).toHaveURL(/\/classroom$/);
  await page.getByLabel("Learning topic").fill("Fractions");
  await page.getByRole("button", { name: /Start classroom/ }).click();
  const question = "Explain fractions briefly in English and Telugu (తెలుగులో).";
  await page.getByLabel("Message your AI tutor").fill(question);
  const tutorResponse = page.waitForResponse(response => response.url().includes("/tutor/sessions/") && response.url().endsWith("/chat") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Send message" }).click();
  expect((await tutorResponse).status()).toBe(503);
  await expect(page.getByRole("alert")).toContainText(/Gemini|AI provider|unavailable/i);
  await expect(page.getByLabel("Message your AI tutor")).toHaveValue(question);
  await expect(page.locator(".cl-message")).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("heading", { name: /Fractions/ })).toBeVisible();
  await expect(page.locator(".cl-message")).toHaveCount(0);

  await page.getByRole("button", { name: /Sign out/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email address").fill(studentEmail);
  await page.locator('input[autocomplete="current-password"]').fill("deliberately-invalid-password");
  await page.getByRole("button", { name: /Sign in/ }).click();
  await expect(page.getByRole("alert")).toContainText(/invalid|incorrect/i);
  await expect(page).toHaveURL(/\/login$/);

  expect(liveAiProviderRequests).toEqual([]);
  expect(apiStatuses.some(item => item.path.endsWith("/auth/register") && item.status === 201)).toBe(true);
  expect(apiStatuses.some(item => item.path.endsWith("/auth/login") && item.status === 200)).toBe(true);
  expect(apiStatuses.some(item => item.path.endsWith("/auth/me") && item.status === 200)).toBe(true);
  expect(apiStatuses.some(item => item.path.endsWith("/chat") && item.status === 503)).toBe(true);
  expect(apiStatuses.some(item => item.path.endsWith("/auth/login") && item.status === 401)).toBe(true);
  expect(apiStatuses.filter(item => item.status === 500)).toEqual([]);
  const expectedBlockedFontHosts = new Set(["fonts.googleapis.com", "fonts.gstatic.com"]);
  expect(failedAssetOrigins.every(host => expectedBlockedFontHosts.has(host))).toBe(true);
  const blockedFontConsoleErrors = browserConsoleErrors.filter(message => message.includes("ERR_NETWORK_ACCESS_DENIED"));
  const expectedInvalidLoginConsoleErrors = browserConsoleErrors.filter(message => message.includes("401 (Unauthorized)"));
  const expectedUnavailableProviderConsoleErrors = browserConsoleErrors.filter(message => message.includes("503 (Service Unavailable)"));
  const unexpectedConsoleErrors = browserConsoleErrors.filter(message =>
    !message.includes("ERR_NETWORK_ACCESS_DENIED") && !message.includes("401 (Unauthorized)") && !message.includes("503 (Service Unavailable)")
  );
  expect(blockedFontConsoleErrors).toHaveLength(failedAssetOrigins.length);
  expect(expectedInvalidLoginConsoleErrors).toHaveLength(1);
  expect(expectedUnavailableProviderConsoleErrors).toHaveLength(1);
  expect(unexpectedConsoleErrors, `Unexpected console errors; HTTP responses: ${failedResponses.join(", ")}`).toEqual([]);
  expect(pageErrors).toEqual([]);
});
