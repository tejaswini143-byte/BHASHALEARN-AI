import { createRequire } from "node:module";
import { resolve } from "node:path";

const requireFromFrontend = createRequire(resolve("frontend", "package.json"));
const { chromium, expect } = requireFromFrontend("@playwright/test");

const frontendUrl = process.env.BHASHALEARN_E2E_FRONTEND_URL || "http://127.0.0.1:5184";
const students = [
  { name: "ADV-01 E2E Student A", email: required("BHASHALEARN_E2E_EMAIL"), password: required("BHASHALEARN_E2E_PASSWORD") },
  { name: "ADV-01 E2E Student B", email: required("BHASHALEARN_E2E_SECOND_EMAIL"), password: required("BHASHALEARN_E2E_SECOND_PASSWORD") },
];

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing local E2E setting: ${name}`);
  return value;
}

const browser = await chromium.launch();
let stage = "initializing registration flow";
let activePage = null;
try {
  for (const student of students) {
    stage = "opening synthetic student registration page";
    const context = await browser.newContext();
    const page = await context.newPage();
    activePage = page;
    await page.goto(`${frontendUrl}/register`);
    stage = "checking registration form";
    await expect(page.getByRole("heading", { name: "Create your account." })).toBeVisible();
    stage = "filling synthetic student name";
    await page.getByLabel("Your name").fill(student.name);
    stage = "filling synthetic student email";
    await page.getByLabel("Email address").fill(student.email);
    stage = "filling synthetic student password";
    await page.getByLabel(/Password/).fill(student.password);
    stage = "submitting synthetic student registration form";
    await page.getByRole("button", { name: /create account/i }).click();

    stage = "checking registration result";
    const duplicate = page.getByRole("alert");
    const result = await Promise.race([
      page.waitForURL(/\/dashboard(?:$|\?)/, { timeout: 15_000 }).then(() => "dashboard"),
      duplicate.waitFor({ state: "visible", timeout: 15_000 }).then(() => "alert"),
    ]);
    if (result === "alert") {
      const message = await duplicate.innerText();
      if (!/email already registered/i.test(message)) {
        throw new Error("Synthetic student registration returned an unexpected application error.");
      }
      stage = "opening existing synthetic account sign-in page";
      await page.goto(`${frontendUrl}/login`);
      stage = "filling existing synthetic account sign-in form";
      await page.getByLabel("Email address").fill(student.email);
      await page.getByLabel(/Password/).fill(student.password);
      stage = "signing in existing synthetic account";
      await page.getByRole("button", { name: /sign in/i }).click();
    }

    stage = "verifying synthetic student dashboard URL";
    await expect(page).toHaveURL(/\/dashboard(?:$|\?)/);
    stage = "verifying synthetic student dashboard heading";
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
    await context.close();
  }
  process.stdout.write("Two synthetic E2E students registered and authenticated through the app UI.\n");
} catch (error) {
  process.stderr.write(`Synthetic E2E registration flow stopped while ${stage} (${error?.name || "unknown error"}); credentials were not displayed.\n`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
