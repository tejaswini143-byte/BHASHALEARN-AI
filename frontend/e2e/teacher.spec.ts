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



test("photo requires consent, previews locally, switches modes and removes",async({page},testInfo)=>{await page.goto("/teacher");const picker=page.getByLabel("Choose full-body teacher photo");await expect(picker).toBeDisabled();await page.getByLabel(/permission to use this person's likeness/i).check();const png=await page.evaluate(async()=>{const c=document.createElement("canvas");c.width=2;c.height=2;const x=c.getContext("2d")!;x.fillStyle="#d78b64";x.fillRect(0,0,2,2);const b=await new Promise<Blob>(r=>c.toBlob(v=>r(v!),"image/png"));return Array.from(new Uint8Array(await b.arrayBuffer()))});await picker.setInputFiles({name:"authorized-person.png",mimeType:"image/png",buffer:Buffer.from(png)});await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toBeVisible();await expect(page.getByText("Photo stays in this browser and is never sent to Gemini or Gnani.")).toBeVisible();await page.getByRole("button",{name:"Holographic teacher"}).click();await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toBeVisible();await page.screenshot({path:testInfo.outputPath("photo-teacher-preview.png"),fullPage:true});await page.getByRole("button",{name:"Remove photo"}).click();await expect(page.getByAltText("Selected teacher photo: authorized-person.png")).toHaveCount(0)});
test("picker rejects spoofed and oversized images",async({page})=>{await page.goto("/teacher");await page.getByLabel(/permission to use this person's likeness/i).check();const p=page.getByLabel("Choose full-body teacher photo");await p.setInputFiles({name:"bad.png",mimeType:"image/png",buffer:Buffer.from("not image")});await expect(page.getByRole("alert").filter({hasText:/does not match/})).toBeVisible();await p.setInputFiles({name:"large.png",mimeType:"image/png",buffer:Buffer.alloc(8*1024*1024+1)});await expect(page.getByRole("alert").filter({hasText:/8 MB/})).toBeVisible()});
test("handoff preserves Telugu language and reports mocked TTS errors",async({page})=>{const tutoring:any[]=[],tts:any[]=[];await page.route("**/api/v1/sessions/s-photo/context**",r=>r.fulfill({json:{session_id:"s-photo",topic:"Fractions",preferred_language:"mixed",learning_level:"beginner",learning_goal:"Halves",learning_pace:"steady",visual_lesson:null}}));let tutorFails=false;await page.route("**/api/v1/tutor/sessions/s-photo/chat",async r=>{tutoring.push(r.request().postDataJSON());if(tutorFails)await r.fulfill({status:502,json:{detail:"Mock tutor unavailable"}});else await r.fulfill({json:{reply:"Mock lesson explanation."}})});await page.route("**/api/v1/voice/sessions/s-photo/speech",async r=>{tts.push(r.request().postDataJSON());await r.fulfill({status:503,json:{detail:"Mock TTS unavailable"}})});await page.goto("/teacher?session=s-photo&question="+encodeURIComponent("\u0c38\u0c17\u0c02 \u0c05\u0c02\u0c1f\u0c47 \u0c0f\u0c2e\u0c3f\u0c1f\u0c3f?"));await expect(page.getByLabel("Explanation language")).toHaveValue("mixed");await page.getByLabel("Explanation language").selectOption("telugu");await page.getByRole("button",{name:"Start explanation"}).click();await expect(page.getByText("Mock lesson explanation.")).toBeVisible();await expect(page.getByRole("alert").filter({hasText:/Mock TTS unavailable/})).toBeVisible();expect(tutoring[0].message).toContain("\u0c38\u0c17\u0c02");expect(tutoring[0].message).toContain("language=telugu");expect(tts[0].language).toBe("telugu");tutorFails=true;await page.getByLabel("Ask another doubt").fill("Give an English example");await page.getByRole("button",{name:"Ask",exact:true}).click();await expect(page.getByRole("alert").filter({hasText:/Mock tutor unavailable/})).toBeVisible()});

test("English student question keeps English lesson context",async({page})=>{
 let request:any;
 await page.route("**/api/v1/sessions/s-english/context**",r=>r.fulfill({json:{session_id:"s-english",topic:"Fractions",preferred_language:"english",learning_level:"beginner",learning_goal:null,learning_pace:"steady",visual_lesson:null}}));
 await page.route("**/api/v1/tutor/sessions/s-english/chat",async r=>{request=r.request().postDataJSON();await r.fulfill({json:{reply:"Mock English explanation."}})});
 await page.route("**/api/v1/voice/sessions/s-english/speech",r=>r.fulfill({status:503,json:{detail:"Mock TTS unavailable"}}));
 await page.goto("/teacher?session=s-english&question=Explain+one-half");
 await expect(page.getByLabel("Explanation language")).toHaveValue("english");
 await page.getByRole("button",{name:"Start explanation"}).click();
 await expect(page.getByText("Mock English explanation.")).toBeVisible();
 expect(request.message).toContain("language=english");
});
