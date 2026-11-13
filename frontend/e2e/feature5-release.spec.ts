import { expect, test } from "@playwright/test";

test("immersive classroom redirects unauthenticated visitors to login", async ({ page }) => {
  await page.goto("/immersive");
  await expect(page).toHaveURL(/\/login(?:[/?#]|$)/);
  await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
});

test("login page remains usable on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/login");
  await expect(page.locator("body")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  expect(hasHorizontalOverflow).toBe(false);
});
