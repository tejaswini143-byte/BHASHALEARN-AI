import { expect, test } from "@playwright/test";
import { writeFile } from "node:fs/promises";

test("Pixiv VRM renders and animates in desktop and mobile teacher studio", async ({ page }, testInfo) => {
  const browserErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("pageerror", error => browserErrors.push(`pageerror: ${error.message}`));
  page.on("requestfailed", request => failedRequests.push(`${request.url()} :: ${request.failure()?.errorText ?? "unknown failure"}`));
  page.on("console", message => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/teacher");
  await expect(page.getByRole("heading", { name: "AI classroom" })).toBeVisible();
  await expect(page.locator(".tp-local-note")).toContainText("AvatarSample_B · Pixiv sample VRM · animated locally", { timeout: 30_000 });

  const canvas = page.locator(".tp-stage-shell canvas");
  await expect(canvas).toBeVisible();
  const webgl = await canvas.evaluate(element => {
    const canvasElement = element as HTMLCanvasElement;
    const context = canvasElement.getContext("webgl2") || canvasElement.getContext("webgl");
    return { available: Boolean(context), width: canvasElement.width, height: canvasElement.height };
  });
  expect(webgl.available).toBe(true);
  expect(webgl.width).toBeGreaterThan(0);
  expect(webgl.height).toBeGreaterThan(0);

  await page.waitForTimeout(500);
  const firstFrame = await canvas.screenshot();
  await page.waitForTimeout(450);
  const nextFrame = await canvas.screenshot();
  expect(Buffer.compare(firstFrame, nextFrame)).not.toBe(0);
  await page.screenshot({ path: testInfo.outputPath("teacher-desktop.png"), fullPage: true });

  await page.getByLabel("Animation").selectOption("explain");
  await page.getByLabel("Expression").selectOption("happy");
  await expect(page.getByLabel("Animation")).toHaveValue("explain");
  await expect(page.getByLabel("Expression")).toHaveValue("happy");
  await page.screenshot({ path: testInfo.outputPath("teacher-explain.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(canvas).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("teacher-mobile.png"), fullPage: true });
  const mobileOverflow = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>("body *")].map(element => {
    const rect = element.getBoundingClientRect();
    return { selector: `${element.tagName.toLowerCase()}.${[...element.classList].join(".")}`, left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width) };
  }).filter(item => item.left < -1 || item.right > window.innerWidth + 1));
  const mobileHasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  expect(mobileHasOverflow, JSON.stringify(mobileOverflow.slice(0, 15))).toBe(false);

  await writeFile(testInfo.outputPath("browser-console-errors.json"), JSON.stringify({ browserErrors, failedRequests }, null, 2));
  expect(browserErrors.filter(error => !error.includes("ERR_NETWORK_ACCESS_DENIED"))).toEqual([]);
  expect(failedRequests.filter(request => !request.includes("fonts.googleapis.com") && !request.includes("fonts.gstatic.com"))).toEqual([]);
});
