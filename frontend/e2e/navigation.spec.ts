import { expect, test } from "@playwright/test";

test("landing navigation supports keyboard use, reduced motion, and narrow screens", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Your language/ })).toBeVisible();
  expect(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
  await expect(page.locator(".floating-card").first()).toHaveCSS("animation-name", "none");

  const menu = page.getByRole("button", { name: "Toggle navigation" });
  for (let i = 0; i < 8; i += 1) {
    if (await menu.evaluate(element => element === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(menu).toBeFocused();
  await expect(menu).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  await expect(menu).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Classroom" })).toBeVisible();
  const overflow = await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>("body *"))
    .filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
    .map(element => ({ tag: element.tagName, className: element.className, right: Math.round(element.getBoundingClientRect().right), text: element.innerText.slice(0, 60) })));
  expect(overflow).toEqual([]);
});
