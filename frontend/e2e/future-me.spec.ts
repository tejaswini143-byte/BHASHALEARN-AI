import { expect, test } from "@playwright/test";

test("Future Me Simulator supports career selection, branching, completion, and replay", async ({ page }) => {
  await page.goto("/future-me");
  await expect(page.getByRole("heading", { name: "Meet a possible future you." })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("do not predict your future");
  await page.getByRole("button", { name: /Software engineer/ }).click();
  await expect(page.getByRole("heading", { name: "What would you do first?" })).toBeVisible();
  await page.getByRole("button", { name: /Reproduce the issue/ }).click();
  await expect(page.getByRole("status")).toContainText("You find that progress is saved only in the current page state.");
  await expect(page.getByRole("heading", { name: /How will you make the next step useful/ })).toBeVisible();
  await page.getByRole("button", { name: /Add a save indicator/ }).click();
  await page.getByRole("button", { name: /Demo the fix/ }).click();
  await expect(page.getByRole("heading", { name: "You explored software engineer." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Skills you practiced" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ideas for what to learn next" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Your path through the scenario" })).toContainText("The team can verify the fix");
  await page.getByRole("button", { name: "Replay this scenario" }).click();
  await expect(page.getByRole("heading", { name: "What would you do first?" })).toBeVisible();
});

test("career selection works with keyboard and controls remain visible on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/future-me");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: /Software engineer/ })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "What would you do first?" })).toBeVisible();
  const firstChoice = page.getByRole("button", { name: /Reproduce the issue/ });
  await firstChoice.scrollIntoViewIfNeeded();
  await expect(firstChoice).toBeInViewport();
});
