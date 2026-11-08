import { expect, test } from "@playwright/test";

async function authenticatePreview(page: import("@playwright/test").Page) {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "int10a-preview-token"));
  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: { id: "int10a-student", email: "student@example.test", display_name: "A Student" } }));
}

test("immersive route preserves student access control", async ({ page }) => {
  await page.goto("/immersive");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Email address")).toBeVisible();
});

test("authenticated student can control the floating lesson and camera", async ({ page }) => {
  await authenticatePreview(page);
  await page.goto("/immersive");
  await expect(page.getByRole("heading", { name: "The Pythagorean theorem" })).toBeVisible();
  await expect(page.getByText("Discover how the squares on a right triangle's sides fit together.")).toBeVisible();
  await page.getByRole("button", { name: "Next lesson step" }).click();
  await expect(page.locator(".ic-step-name")).toContainText("Find the right angle");
  await page.getByRole("button", { name: "Next lesson step" }).click();
  await expect(page.locator(".ic-step-name")).toContainText("Square each leg");
  await page.getByRole("button", { name: /Lesson/ }).click();
  await expect(page.getByRole("button", { name: /Lesson/ })).toHaveAttribute("aria-pressed", "true");
  await page.locator(".ic-scene").click({ position: { x: 40, y: 170 } });
  await page.keyboard.press("ArrowRight");
  await expect(page.locator(".ic-step-name")).toContainText("Take the square root");
  await page.keyboard.press("3");
  await expect(page.getByRole("button", { name: /Lesson/ })).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("Choose lesson").selectOption("1");
  await expect(page.getByRole("heading", { name: "A tour of the solar system" })).toBeVisible();
  await page.getByLabel("Reduce motion").check();
  await expect(page.getByLabel("Reduce motion")).toBeChecked();
  await page.getByRole("button", { name: "Play lesson" }).click();
  await expect(page.locator(".ic-step-name")).toContainText("Start with the Sun");
  const classroom = page.getByRole("main", { name: "Immersive classroom" });
  await expect(classroom).not.toContainText(/smartboard|whiteboard|projector/i);
  await expect(classroom.locator("[aria-label='smartboard' i], [aria-label='whiteboard' i], [aria-label='projector' i]")).toHaveCount(0);
});

test("WebGL failure leaves lesson navigation available", async ({ page }) => {
  await authenticatePreview(page);
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type: string, ...args: unknown[]) {
      if (["webgl", "webgl2", "experimental-webgl"].includes(type)) return null;
      return original.call(this, type, ...args as [any]);
    };
  });
  await page.goto("/immersive");
  await expect(page.getByRole("heading", { name: "3D view unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Next lesson step" })).toBeVisible();
  await page.getByLabel("Choose lesson").selectOption("2");
  await expect(page.getByRole("heading", { name: "Everyday words: Telugu ↔ English" })).toBeVisible();
});

test("small screens keep lesson and camera controls inside the viewport", async ({ page }) => {
  await authenticatePreview(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/immersive");
  await expect(page.getByRole("heading", { name: "The Pythagorean theorem" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Next lesson step" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Camera presets" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});
