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
  await page.locator('input[type="file"][accept=".glb,model/gltf-binary"]').setInputFiles({ name: "invalid.glb", mimeType: "model/gltf-binary", buffer: Buffer.from("not a glTF binary") });
  await expect(page.getByText("Could not read that GLB. The geometric preview remains available.")).toBeVisible();
});

test("photo teacher requires likeness permission, previews locally and switches modes", async ({ page }) => {
  await page.goto("/teacher");
  const picker = page.getByLabel("Choose full-body teacher photo");
  await expect(picker).toBeDisabled();
  await page.getByLabel(/permission to use this person's likeness/i).check();
  const png = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 2;
    canvas.height = 2;
    const context = canvas.getContext("2d")!;
    context.fillStyle = "#d78b64";
    context.fillRect(0, 0, 2, 2);
    const blob = await new Promise<Blob>(resolve => canvas.toBlob(value => resolve(value!), "image/png"));
    return Array.from(new Uint8Array(await blob.arrayBuffer()));
  });
  await picker.setInputFiles({ name: "authorized-person.png", mimeType: "image/png", buffer: Buffer.from(png) });
  await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toBeVisible();
  await expect(page.getByText("Photo stays in this browser and is never sent to Gemini or Gnani.")).toBeVisible();

  const bridgeState = async (state: "speaking" | "idle") => page.evaluate(async value => {
    const { immersiveVoiceBridge } = await import("/src/immersiveVoiceBridge.ts");
    immersiveVoiceBridge.setState(value as "speaking" | "idle");
  }, state);
  await bridgeState("speaking");
  await expect(page.getByRole("status").filter({ hasText: "Teacher speech playing" })).toBeVisible();
  await bridgeState("idle");

  await page.getByRole("button", { name: "Holographic teacher" }).click();
  await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toBeVisible();
  await expect(page.getByText("Photo teacher · static appearance")).toBeVisible();
  await page.getByRole("button", { name: "Human teacher" }).click();
  await page.getByRole("button", { name: "Remove photo" }).click();
  await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toHaveCount(0);
});

test("photo picker rejects spoofed and oversized files and consent revocation removes selection", async ({ page }) => {
  await page.goto("/teacher");
  await page.getByLabel(/permission to use this person's likeness/i).check();
  const picker = page.getByLabel("Choose full-body teacher photo");
  await picker.setInputFiles({ name: "bad.png", mimeType: "image/png", buffer: Buffer.from("not image") });
  await expect(page.getByRole("alert").filter({ hasText: /does not match/ })).toBeVisible();
  await picker.setInputFiles({ name: "large.png", mimeType: "image/png", buffer: Buffer.alloc(8 * 1024 * 1024 + 1) });
  await expect(page.getByRole("alert").filter({ hasText: /8 MB/ })).toBeVisible();

  const png = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 2;
    canvas.height = 2;
    const blob = await new Promise<Blob>(resolve => canvas.toBlob(value => resolve(value!), "image/png"));
    return Array.from(new Uint8Array(await blob.arrayBuffer()));
  });
  await picker.setInputFiles({ name: "authorized-person.png", mimeType: "image/png", buffer: Buffer.from(png) });
  await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toBeVisible();
  await page.getByLabel(/permission to use this person's likeness/i).uncheck();
  await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toHaveCount(0);
  await expect(picker).toBeDisabled();
});
