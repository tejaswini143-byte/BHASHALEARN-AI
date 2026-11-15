import { test, expect } from "@playwright/test";
import { allowAuthenticatedTests, requireDedicatedLogin, signIn, testEmail, testPassword } from "./helpers";

test("login form is rendered and a real HTTP 401 is reported as an authentication error", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome Back" })).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
  await expect(page.getByLabel(/Password/)).toBeVisible();
  await page.getByLabel("Email address").fill("adv01-invalid-credentials@example.com");
  await page.getByLabel(/Password/).fill("deliberately-invalid-e2e-password");
  const responsePromise = page.waitForResponse(response => response.url().includes("/api/v1/auth/login"));
  await page.getByRole("button", { name: /sign in/i }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(401);
  await expect(page.getByRole("alert")).toContainText(/invalid email or password/i);
  await expect(page.getByRole("alert")).not.toContainText(/cannot connect to the backend/i);
});

test("registration requires a matching confirmation before using the existing auth API", async ({ page }) => {
  let registerBody: unknown;
  let loginBody: unknown;
  await page.route("**/api/v1/auth/register", async route => {
    registerBody = route.request().postDataJSON();
    await route.fulfill({ json: { id: "registration-test", email: "student@example.test", display_name: "Meera Student" } });
  });
  await page.route("**/api/v1/auth/login", async route => {
    loginBody = route.request().postDataJSON();
    await route.fulfill({ json: { access_token: "registration-test-token", token_type: "bearer" } });
  });
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Meera Student");
  await page.getByLabel("Email address").fill("student@example.test");
  await page.getByLabel(/^Password/).fill("correct-horse-battery");
  await page.getByLabel("Confirm password").fill("different-horse-battery");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.getByRole("alert")).toHaveText("Passwords do not match.");
  expect(registerBody).toBeUndefined();
  await page.getByLabel("Confirm password").fill("correct-horse-battery");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(registerBody).toEqual({ email: "student@example.test", display_name: "Meera Student", password: "correct-horse-battery" });
  expect(loginBody).toEqual({ email: "student@example.test", password: "correct-horse-battery" });
});

test("a network failure is described as an API connection failure", async ({ page }) => {
  await page.route("**/api/v1/auth/login", route => route.abort("failed"));
  await page.goto("/login");
  await page.getByLabel("Email address").fill("adv01-network-failure@example.com");
  await page.getByLabel(/Password/).fill("not-a-real-password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("alert")).toContainText(/cannot connect to the backend/i);
});

test("protected dashboard redirects unauthenticated visitors to login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Email address")).toBeVisible();
});

test("dedicated student can log in, retain the session after refresh, and sign out", async ({ page }) => {
  test.skip(!allowAuthenticatedTests || !requireDedicatedLogin(), "Set explicit dedicated E2E student credentials and allow authenticated reads.");
  await signIn(page, testEmail, testPassword);
  await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/);
});
