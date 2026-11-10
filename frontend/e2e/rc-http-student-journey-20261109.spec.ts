import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("real HTTP student journey persists a clearly labeled local tutor stub", async ({ page }) => {
  const studentEmail = `rc-student-${Date.now()}@example.com`;
  const password = `Synthetic-${randomUUID()}-e2e!`;
  const apiStatuses: Array<{ path: string; status: number }> = [];
  const liveAiProviderRequests: string[] = [];
  const browserConsoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedAssetOrigins: string[] = [];

  page.on("request", request => {
    const host = new URL(request.url()).hostname.toLowerCase();
    if (host === "generativelanguage.googleapis.com" || host.endsWith(".gnani.ai")) liveAiProviderRequests.push(host);
  });
  page.on("response", response => {
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/v1/")) apiStatuses.push({ path: url.pathname, status: response.status() });
  });
  page.on("console", message => {
    if (message.type() === "error") browserConsoleErrors.push(message.text());
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
  await page.getByLabel("Message your AI tutor").fill("Explain fractions briefly in English and Telugu (తెలుగులో).");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText(/TEST STUB.*not a Gemini response/)).toBeVisible();
  await expect(page.getByText(/తెలుగులో:/)).toBeVisible();

  await page.reload();
  await expect(page.getByText(/TEST STUB.*not a Gemini response/)).toBeVisible();
  await expect(page.getByText("Explain fractions briefly in English and Telugu (తెలుగులో).", { exact: true })).toBeVisible();

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
  expect(apiStatuses.some(item => item.path.endsWith("/chat") && item.status === 200)).toBe(true);
  expect(apiStatuses.some(item => item.path.endsWith("/auth/login") && item.status === 401)).toBe(true);
  expect(apiStatuses.filter(item => item.status >= 500)).toEqual([]);
  const expectedBlockedFontHosts = new Set(["fonts.googleapis.com", "fonts.gstatic.com"]);
  expect(failedAssetOrigins.every(host => expectedBlockedFontHosts.has(host))).toBe(true);
  const blockedFontConsoleErrors = browserConsoleErrors.filter(message => message.includes("ERR_NETWORK_ACCESS_DENIED"));
  const expectedInvalidLoginConsoleErrors = browserConsoleErrors.filter(message => message.includes("401 (Unauthorized)"));
  const unexpectedConsoleErrors = browserConsoleErrors.filter(message =>
    !message.includes("ERR_NETWORK_ACCESS_DENIED") && !message.includes("401 (Unauthorized)")
  );
  expect(blockedFontConsoleErrors).toHaveLength(failedAssetOrigins.length);
  expect(expectedInvalidLoginConsoleErrors).toHaveLength(1);
  expect(unexpectedConsoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
