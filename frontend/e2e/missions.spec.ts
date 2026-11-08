import { expect, test } from "@playwright/test";

test("Mission Mode shows progress and clear reward feedback after a claim", async ({ page }) => {
  let claimed = false;
  const mission = (id: string, title: string, progress: number, target: number, xp_reward: number, daily = false) => ({
    id, title, subject: id.includes("path") ? "Computer Science" : "Mathematics",
    description: "A focused learning quest.", objective: `Answer ${target} questions correctly`, progress, target,
    xp_reward, completed: claimed && id === "quest-fractions", eligible: progress >= target && !(claimed && id === "quest-fractions"),
    completed_at: null, daily, active_date: daily ? "2026-11-08" : null,
  });
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "browser-test-token"));
  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: { id: "student-1", display_name: "Test Learner", email: "test@example.com" } }));
  await page.route("**/api/v1/missions", route => route.fulfill({ json: {
    missions: [mission("quest-fractions", "Fraction Explorer", 3, 3, 60),
      mission("quest-pathfinder", "Pathfinder", 0, 3, 75), mission("daily-2026-11-08", "Fraction Flash", 0, 1, 25, true)],
    xp: claimed ? 60 : 0, level: 1, xp_into_level: claimed ? 60 : 0,
    xp_to_next_level: claimed ? 40 : 100, badges: claimed ? ["First Steps"] : [],
  } }));
  await page.route("**/api/v1/missions/quest-fractions/claim", async route => {
    claimed = true;
    await route.fulfill({ json: { xp_awarded: 60, total_xp: 60, level: 1, replayed: false, feedback: "Mission complete! +60 XP earned." } });
  });

  await page.goto("/missions");
  await expect(page.getByRole("heading", { name: "Mission Mode" })).toBeVisible();
  await expect(page.getByRole("link", { name: "AI Classroom" })).toHaveAttribute("href", "/classroom");
  await expect(page.getByText("Complete the matching objective quiz in AI Classroom")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fraction Explorer" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Fraction Explorer progress" })).toHaveAttribute("aria-valuenow", "3");
  await page.getByRole("button", { name: "Claim reward" }).click();
  await expect(page.getByRole("status")).toContainText("Mission complete! +60 XP earned.");
  await expect(page.getByRole("heading", { name: "Fraction Explorer" }).locator(".." ).getByText("Reward claimed")).toBeVisible();
  await expect(page.getByLabel("Progress to next level")).toHaveAttribute("aria-valuenow", "60");
  await expect(page.getByText("First Steps")).toBeVisible();
});
