import { expect, test } from "@playwright/test";

async function authenticate(page: import("@playwright/test").Page) {
  await page.addInitScript(() => sessionStorage.setItem("bhashalearn_access_token", "int15-mock-token"));
  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: { id: "int15-student", email: "student@example.test", display_name: "A Student" } }));
}

test("visual lessons route requires an authenticated student", async ({ page }) => {
  await page.goto("/visual-lessons");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Email address")).toBeVisible();
});

test("student selects subject and topic and explores solar system controls", async ({ page }) => {
  await authenticate(page);
  await page.goto("/visual-lessons");
  await expect(page.getByRole("heading", { name: "A tour of the solar system" })).toBeVisible();
  await expect(page.getByText("Educational model: planet sizes, orbit spacing, and distances are not proportional to real scale.")).toBeVisible();
  await page.getByRole("button", { name: "Mars", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mars", exact: true })).toBeVisible();
  await expect(page.getByText("A cold, rocky planet often called the red planet.")).toBeVisible();
  const scale = page.getByLabel("Time scale");
  await scale.focus(); await scale.press("ArrowRight");
  await expect(scale).toHaveValue("31");
  await page.getByLabel("Choose subject").selectOption("Mathematics");
  await page.getByLabel("Choose topic").selectOption("geometry");
  await expect(page.getByRole("heading", { name: "Inspect 3D shapes" })).toBeVisible();
});

test("geometry controls expose shape facts and computed dimensions", async ({ page }) => {
  await authenticate(page);
  await page.goto("/visual-lessons");
  await page.getByLabel("Choose subject").selectOption("Mathematics");
  await page.getByLabel("Choose topic").selectOption("geometry");
  await page.getByLabel("Choose shape").selectOption("sphere");
  await expect(page.getByText("sphere · 0 faces · 0 edges · 0 vertices")).toBeVisible();
  await expect(page.getByText(/V = 4πr³\/3/)).toBeVisible();
  await page.getByLabel("Explanation language").selectOption("te");
  await expect(page.getByRole("heading", { name: "త్రిమితీయ ఆకారాలను పరిశీలించండి" })).toBeVisible();
  await expect(page.locator(".vl-facts p")).toContainText("దాని ఉపరితలం వక్రంగా ఉంటుంది");
});

test("pendulum controls calculate period and support pause, resume, reset and guided steps", async ({ page }) => {
  await authenticate(page);
  await page.goto("/visual-lessons");
  await page.getByLabel("Choose subject").selectOption("Physics");
  await page.getByLabel("Choose topic").selectOption("pendulum");
  await expect(page.getByText("T ≈ 2.01 s")).toBeVisible();
  await page.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByText(/Motion running/)).toBeVisible();
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText(/Paused/)).toBeVisible();
  await page.getByRole("button", { name: "Resume" }).click();
  await page.getByRole("button", { name: "Reset lesson" }).click();
  await expect(page.getByRole("button", { name: "Resume" })).toBeVisible();
  await page.getByRole("heading", { name: "Pendulum motion" }).click();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("heading", { name: "Set the length" })).toBeVisible();
});

test("WebGL failure keeps text explanations and controls available", async ({ page }) => {
  await authenticate(page);
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type: string, ...args: unknown[]) {
      if (["webgl", "webgl2", "experimental-webgl"].includes(type)) return null;
      return original.call(this, type, ...args as [any]);
    };
  });
  await page.goto("/visual-lessons");
  await expect(page.getByRole("alert").filter({ hasText: "3D simulation unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Next lesson step" })).toBeVisible();
  await expect(page.getByText("LEARNING OBJECTIVES")).toBeVisible();
});

test("mobile visual lessons fit the viewport and keyboard reset works", async ({ page }) => {
  await authenticate(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/visual-lessons");
  await expect(page.getByRole("heading", { name: "A tour of the solar system" })).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("heading", { name: "Meet the Sun" })).toBeVisible();
  await page.keyboard.press("r");
  await expect(page.getByRole("heading", { name: "Start exploring" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
