import { expect, test } from "@playwright/test";

test("3D teacher preview exposes the classroom and working lesson controls", async ({ page }) => {
  await page.goto("/teacher");
  await expect(page.getByRole("heading", { name: "Meet your AI teacher." })).toBeVisible();
  await expect(page.getByRole("region", { name: "Interactive 3D classroom" })).toBeVisible();
  const canvas = page.locator(".tp-stage-shell canvas");
  await expect(canvas).toBeVisible();
  expect(await canvas.evaluate(element => Boolean((element as HTMLCanvasElement).getContext("webgl2") || (element as HTMLCanvasElement).getContext("webgl")))).toBeTruthy();
  await expect(page.getByLabel("Animation")).toHaveValue("idle");
  await page.getByLabel("Animation").selectOption("listen");
  await expect(page.getByLabel("Animation")).toHaveValue("listen");
  await page.getByLabel("Expression").selectOption("curious");
  await expect(page.getByLabel("Expression")).toHaveValue("curious");
  await page.getByRole("button", { name: "Play synthetic viseme demo" }).click();
  await expect(page.getByRole("button", { name: "Stop synthetic viseme demo" })).toBeVisible();
  await page.getByLabel("Board position").selectOption("0.28,0.58");
  await expect(page.getByText("Look at the highlighted board position")).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({ name: "invalid.glb", mimeType: "model/gltf-binary", buffer: Buffer.from("not a glTF binary") });
  await expect(page.getByText("Could not read that GLB. The geometric preview remains available.")).toBeVisible();
});
