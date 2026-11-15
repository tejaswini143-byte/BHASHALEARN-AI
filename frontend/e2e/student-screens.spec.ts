import { expect, test } from "@playwright/test";

const profile = { id: "student-1", email: "student@example.test", display_name: "Meera Student" };
const preferences = { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: "Speak Telugu with confidence" };

async function signIn(page) {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "e2e-student-token"));
}

test("settings reads account data and saves profile and language preferences", async ({ page }) => {
  await signIn(page);
  let profilePatch: unknown;
  let preferencePut: unknown;
  await page.route("**/api/v1/students/me", async route => {
    if (route.request().method() === "PATCH") {
      profilePatch = route.request().postDataJSON();
      await route.fulfill({ json: { ...profile, ...(profilePatch as object) } });
    } else await route.fulfill({ json: profile });
  });
  await page.route("**/api/v1/students/me/preferences", async route => {
    if (route.request().method() === "PUT") {
      preferencePut = route.request().postDataJSON();
      await route.fulfill({ json: preferencePut });
    } else await route.fulfill({ json: preferences });
  });

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await page.getByLabel("Full name").fill("Meera Learner");
  await page.getByLabel("Language").selectOption("telugu");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText("saved to your account");
  expect(profilePatch).toEqual({ display_name: "Meera Learner" });
  expect(preferencePut).toMatchObject({ preferred_language: "telugu", learning_goal: preferences.learning_goal });
});

test("timeline renders only recorded account activity and stays within a mobile viewport", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/analytics?range_days=7", route => route.fulfill({ json: {
    recent_activity: [{ kind: "session", title: "Fractions practice", detail: "2 answers recorded", occurred_at: "2026-11-15T08:00:00Z" }],
    trend: [{ date: "2026-11-15", activity_count: 2, sessions: 1 }, { date: "2026-11-14", activity_count: 0, sessions: 0 }],
    overview: { learning_time_minutes: null, learning_time_status: "unavailable" },
  } }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/timeline");
  await expect(page.getByText("Fractions practice")).toBeVisible();
  await expect(page.getByText("2 recorded learning activities")).toBeVisible();
  await expect(page.getByText("No recorded sessions")).toBeVisible();
  const overflow = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth, offenders: [...document.querySelectorAll("body *")].map(el => ({ tag: el.tagName, className: typeof el.className === "string" ? el.className : "", width: Math.round(el.getBoundingClientRect().width), right: Math.round(el.getBoundingClientRect().right) })).filter(el => el.right > window.innerWidth + 1).slice(0, 8) }));
  expect(overflow.document, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.viewport);
});

test("certificate route withholds certificate until the account course is completed", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/students/me", route => route.fulfill({ json: profile }));
  await page.route("**/api/v1/courses/catalog", route => route.fulfill({ json: [
    { id: "telugu-basics", title: "Telugu Basics", description: "", language: "telugu", completed: false, enrolled: true, lessons_count: 5, lessons_completed: 2, progress_percent: 40, enrolled_at: "2026-11-01T00:00:00Z" },
  ] }));
  await page.goto("/certificate");
  await expect(page.getByRole("heading", { name: "No certificates yet" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Explore courses" })).toBeVisible();
});

test("certificate print view uses actual eligible course and student data", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/students/me", route => route.fulfill({ json: profile }));
  await page.route("**/api/v1/courses/catalog", route => route.fulfill({ json: [
    { id: "telugu-basics", title: "Telugu Basics", description: "", language: "telugu", completed: true, enrolled: true, lessons_count: 5, lessons_completed: 5, progress_percent: 100, enrolled_at: "2026-11-01T00:00:00Z" },
  ] }));
  await page.goto("/certificate");
  await expect(page.getByText("Meera Student", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Telugu Basics" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Print certificate" })).toBeVisible();
});

test("forgot password requests a reset without disclosing whether an email exists", async ({ page }) => {
  let requested: unknown;
  await page.route("**/api/v1/auth/password-reset/request", async route => {
    requested = route.request().postDataJSON();
    await route.fulfill({ status: 202, json: { message: "If an account exists for that address, a reset link will be sent." } });
  });
  await page.goto("/forgot-password");
  await page.getByLabel("Email address").fill("student@example.test");
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByRole("status")).toContainText("If an account exists");
  expect(requested).toEqual({ email: "student@example.test" });
});

test("reset form requires matching password and carries its one-use token", async ({ page }) => {
  let requestBody: unknown;
  await page.route("**/api/v1/auth/password-reset/complete", async route => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({ json: { message: "Your password has been updated." } });
  });
  await page.goto("/reset-password?token=one-time-reset-token-012345678901234567890123");
  await page.getByRole("textbox", { name: "New password", exact: true }).fill("correct-horse-battery-staple");
  await page.getByRole("textbox", { name: "Confirm new password", exact: true }).fill("different-password-value");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByRole("alert")).toHaveText("Passwords do not match.");
  expect(requestBody).toBeUndefined();
  await page.getByRole("textbox", { name: "Confirm new password", exact: true }).fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByRole("status")).toContainText("password has been updated");
  expect(requestBody).toEqual({ token: "one-time-reset-token-012345678901234567890123", password: "correct-horse-battery-staple" });
});
