import { expect, test } from "@playwright/test";

test("holographic lesson exposes working teacher poses and spatial explanations", async ({ page }) => {
  await page.goto("/holographic-teacher");
  await expect(page.getByRole("heading", { name: "Learn in three dimensions." })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("No licensed rigged avatar");
  await expect(page.getByLabel("Interactive holographic classroom").locator("canvas")).toBeVisible();
  await page.getByLabel("Spatial lesson").selectOption("fractions");
  await expect(page.getByRole("heading", { name: "Equivalent fractions" })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Teacher and lesson controls" }).getByText("1/2 = 2/4")).toBeVisible();
  await page.getByRole("button", { name: "Point to explanation" }).click();
  await expect(page.getByLabel("Teacher state")).toHaveValue("pointing");
  await page.getByLabel("Reduce motion").check({ force: true });
  await expect(page.getByLabel("Reduce motion")).toBeChecked();
  await page.getByLabel("Low-performance graphics").check({ force: true });
  await expect(page.getByLabel("Low-performance graphics")).toBeChecked();
  await expect(page.getByLabel("Interactive holographic classroom")).not.toContainText(/blackboard|smartboard|projector/i);
});

test("WebGL unavailable fallback keeps lesson controls available", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type: string, ...args: unknown[]) {
      if (["webgl", "webgl2", "experimental-webgl"].includes(type)) return null;
      return original.call(this, type, ...args as [any]);
    };
  });
  await page.goto("/holographic-teacher");
  await expect(page.getByText("3D view unavailable")).toBeVisible();
  await expect(page.getByLabel("Spatial lesson")).toBeVisible();
  await page.getByLabel("Spatial lesson").selectOption("solar");
  await expect(page.getByRole("heading", { name: "Planetary orbits" })).toBeVisible();
});

test("teacher scene stays inside a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/holographic-teacher");
  await expect(page.getByLabel("Teacher state")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
