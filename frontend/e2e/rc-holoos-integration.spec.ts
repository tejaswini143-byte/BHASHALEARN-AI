import { expect, test } from "@playwright/test";

const token = "rc-holoos-navigation-token";

test("HoloOS command center exposes Immersive Classroom, Future Me, and Learning Memories", async ({ page }) => {
  await page.addInitScript(value => sessionStorage.setItem("bhashalearn_access_token", value), token);
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { id: "student-1", email: "preview@example.test", display_name: "Preview Learner" } });
    } else if (path.endsWith("/progress") || path.endsWith("/sessions")) {
      await route.fulfill({ json: [] });
    } else if (path.endsWith("/students/me/preferences")) {
      await route.fulfill({ json: { preferred_language: "mixed", learning_level: "beginner", learning_goal: null } });
    } else if (path.endsWith("/missions")) {
      await route.fulfill({ json: { missions: [], xp: 0, level: 1, xp_into_level: 0, xp_to_next_level: 100, badges: [] } });
    } else if (path.endsWith("/memories")) {
      await route.fulfill({ json: [] });
    } else {
      await route.fulfill({ json: {} });
    }
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: /good to see you, preview/i })).toBeVisible();

  const menu = page.locator(".cc-menu");
  await menu.focus();
  await page.keyboard.press("Enter");
  await expect(menu).toHaveAttribute("aria-expanded", "true");

  for (const [name, href] of [
    [/Immersive AI classroom/, "/immersive"],
    [/Future Me simulator/, "/future-me"],
    [/Learning memories/, "/memories"],
  ] as const) {
    const link = page.getByRole("link", { name }).first();
    await expect(link).toHaveAttribute("href", href);
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${href.replaceAll("/", "\\/")}(?:$|[?#])`));
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /good to see you, preview/i })).toBeVisible();
    if (href !== "/memories") {
      await page.getByRole("button", { name: "Open dashboard navigation" }).click();
    }
  }

  await page.getByRole("button", { name: "Open dashboard navigation" }).focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Open dashboard navigation" })).toBeFocused();
  await expect(page.getByRole("button", { name: "Open dashboard navigation" })).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#dashboard-sidebar")).not.toHaveClass(/\bopen\b/);
});
