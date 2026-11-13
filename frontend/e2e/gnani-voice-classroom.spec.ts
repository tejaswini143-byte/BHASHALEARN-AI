import { expect, test, type Page } from "@playwright/test";

// Explicitly mocked browser coverage. The routes below never contact Gnani,
// Gemini, or a real classroom account.
const session = { id: "voice-classroom-test", topic: "Fractions", language: "mixed", created_at: "2026-11-09T10:00:00Z" };
const prefs = { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null };
const transcript = "నమస్కారం! What is one half?";
const reply = { reply: "One of two equal parts.", session_id: session.id, language: "mixed", learning_level: "beginner" };

function pcmWav(): Buffer {
  const rate = 16000;
  const samples = rate;
  const bytes = Buffer.alloc(44 + samples * 2);
  bytes.write("RIFF", 0); bytes.writeUInt32LE(bytes.length - 8, 4); bytes.write("WAVE", 8);
  bytes.write("fmt ", 12); bytes.writeUInt32LE(16, 16); bytes.writeUInt16LE(1, 20); bytes.writeUInt16LE(1, 22);
  bytes.writeUInt32LE(rate, 24); bytes.writeUInt32LE(rate * 2, 28); bytes.writeUInt16LE(2, 32); bytes.writeUInt16LE(16, 34);
  bytes.write("data", 36); bytes.writeUInt32LE(samples * 2, 40);
  for (let i = 0; i < samples; i += 1) bytes.writeInt16LE(Math.round(Math.sin(i * 2 * Math.PI * 220 / rate) * 4000), 44 + i * 2);
  return bytes;
}

async function startRecording(page: Page, approve = true) {
  await Promise.all([
    page.waitForEvent("dialog").then(async dialog => {
      expect(dialog.type()).toBe("confirm");
      expect(dialog.message()).toContain("start recording your microphone locally");
      if (approve) await dialog.accept();
      else await dialog.dismiss();
    }),
    page.getByRole("button", { name: "Start microphone recording" }).dispatchEvent("click"),
  ]);
}

async function stopRecording(page: Page) {
  await page.getByRole("button", { name: "Stop recording" }).dispatchEvent("click");
}

async function mockVoiceBrowser(page: Page, options: { micDenied?: boolean; sttStatus?: number; ttsStatus?: number; transcript?: string } = {}) {
  await page.addInitScript(({ micDenied }) => {
    sessionStorage.setItem("bhashalearn_access_token", "mock-browser-token");
    const testWindow = window as Window & { voiceTest?: { micCalls: number; tracksStopped: number; recordedFormat?: string; recordedSize?: number } };
    testWindow.voiceTest = { micCalls: 0, tracksStopped: 0 };
    Object.defineProperty(window, "AudioContext", { configurable: true, value: class {
      sampleRate = 48000;
      state = "running";
      destination = {};
      resume = async () => undefined;
      close = async () => { this.state = "closed"; };
      createMediaStreamSource = () => ({ connect: () => undefined, disconnect: () => undefined });
      createGain = () => ({ gain: { value: 1 }, connect: () => undefined, disconnect: () => undefined });
      createScriptProcessor = () => {
        const processor: { onaudioprocess: null | ((event: { inputBuffer: { getChannelData: (_channel: number) => Float32Array } }) => void); connect: () => void; disconnect: () => void } = {
          onaudioprocess: null,
          connect: () => processor.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array(4096).fill(0.15) } }),
          disconnect: () => undefined,
        };
        return processor;
      };
    } });
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
      getUserMedia: async () => {
        testWindow.voiceTest!.micCalls += 1;
        if (micDenied) throw new DOMException("mock denial", "NotAllowedError");
        return { getTracks: () => [{ stop: () => { testWindow.voiceTest!.tracksStopped += 1; } }] };
      },
    } });

    // The test audio is a mocked WAV. Simulate its playback clock so pause,
    // resume, and stop behavior can be asserted without audio hardware.
    const proto = HTMLMediaElement.prototype;
    proto.play = function(this: HTMLMediaElement) {
      const audio = this as HTMLMediaElement & { __time?: number; __paused?: boolean; __ended?: boolean; __timer?: number };
      if (!audio.src.startsWith("blob:")) return Promise.reject(new Error("unexpected non-mock audio"));
      if (audio.__timer) window.clearInterval(audio.__timer);
      audio.__time ??= 0; audio.__paused = false; audio.__ended = false;
      Object.defineProperty(audio, "currentTime", { configurable: true, get: () => audio.__time, set: value => { audio.__time = Number(value) || 0; audio.__ended = false; } });
      Object.defineProperty(audio, "duration", { configurable: true, get: () => 8 });
      Object.defineProperty(audio, "paused", { configurable: true, get: () => audio.__paused });
      Object.defineProperty(audio, "ended", { configurable: true, get: () => audio.__ended });
      audio.dispatchEvent(new Event("play"));
      audio.__timer = window.setInterval(() => {
        if (audio.__paused) return;
        audio.__time = (audio.__time || 0) + 0.05;
        audio.dispatchEvent(new Event("timeupdate"));
        if (audio.__time >= 8) { audio.__ended = true; audio.__paused = true; window.clearInterval(audio.__timer); audio.dispatchEvent(new Event("ended")); }
      }, 50);
      return Promise.resolve();
    };
    proto.pause = function(this: HTMLMediaElement) {
      const audio = this as HTMLMediaElement & { __paused?: boolean };
      if (audio.src.startsWith("blob:") && audio.__paused === false) { audio.__paused = true; audio.dispatchEvent(new Event("pause")); }
    };
  }, { micDenied: options.micDenied ?? false });

  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: { id: "mock-student", email: "learner@example.test", display_name: "Voice Learner" } }));
  await page.route("**/api/v1/sessions?limit=100", route => route.fulfill({ json: [session] }));
  await page.route("**/api/v1/students/me/preferences", route => route.fulfill({ json: prefs }));  await page.route("**/api/v1/voice/sessions/provider-mode", route => route.fulfill({ json: { mode: "unavailable", configured: false } }));
  const initialVoiceState = { session_id: session.id, topic: session.topic, lesson_step: "introduction", student_question: null, active_response_language: "mixed", playback_state: "idle", voice_transcript: null, checkpoint_message_id: null, checkpoint_playback_ms: null, resume_status: "none", updated_at: "2026-11-09T10:00:00Z" };
  await page.route(`**/api/v1/voice/sessions/${session.id}/state`, async route => {
    if (route.request().method() === "GET") return route.fulfill({ json: initialVoiceState });
    const update = route.request().postDataJSON() as Partial<typeof initialVoiceState>;
    return route.fulfill({ json: { ...initialVoiceState, ...update } });
  });
  await page.route(`**/api/v1/sessions/${session.id}/context?limit=500`, route => route.fulfill({ json: {
    session_id: session.id, topic: session.topic, preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null,
    messages: [], visual_lesson: null,
  } }));
  await page.route(`**/api/v1/voice/sessions/${session.id}/transcribe`, async route => {
    const request = route.request();
    const body = await request.postDataBuffer();
    const raw = body?.toString("latin1") ?? "";
    await page.evaluate(({ contentType, size, hasWaveHeader }) => {
      const voiceTest = (window as Window & { voiceTest: { recordedFormat?: string; recordedSize?: number; isPcmWav?: boolean } }).voiceTest;
      voiceTest.recordedFormat = contentType; voiceTest.recordedSize = size; voiceTest.isPcmWav = hasWaveHeader;
    }, { contentType: request.headers()["content-type"], size: body?.byteLength ?? 0, hasWaveHeader: raw.includes("RIFF") && raw.includes("WAVE") && raw.includes("fmt ") });
    await route.fulfill(options.sttStatus && options.sttStatus !== 200
      ? { status: options.sttStatus, json: { detail: "Mock Prisma unavailable." } }
      : { json: { session_id: session.id, transcript: options.transcript ?? transcript, detected_language: "te+en", language_mode: "mixed" } });
  });
  await page.route(`**/api/v1/tutor/sessions/${session.id}/chat`, route => route.fulfill({ json: reply }));
  await page.route(`**/api/v1/voice/sessions/${session.id}/speech`, route => options.ttsStatus && options.ttsStatus !== 200
    ? route.fulfill({ status: options.ttsStatus, json: { detail: "Mock Timbre unavailable." } })
    : route.fulfill({ status: 200, contentType: "audio/wav", body: pcmWav() }));
  await page.goto("/voice");
  await expect(page.getByRole("heading", { name: "Fractions" })).toBeVisible();
}

test.describe("Mocked Gnani voice classroom (no live provider calls)", () => {
  test("dismissing consent preserves the local preview without reopening the microphone or uploading", async ({ page }) => {
    await mockVoiceBrowser(page);
    const micCalls = () => page.evaluate(() => (window as Window & { voiceTest: { micCalls: number } }).voiceTest.micCalls);
    await startRecording(page, false);
    expect(await micCalls()).toBe(0);
    await startRecording(page);
    await stopRecording(page);
    const preview = page.getByLabel("Play back captured microphone audio locally");
    await expect(preview).toBeVisible();
    const previewUrl = await preview.getAttribute("src");
    await startRecording(page, false);
    expect(await micCalls()).toBe(1);
    await expect(preview).toHaveAttribute("src", previewUrl!);
    expect(await page.evaluate(() => (window as Window & { voiceTest: { recordedSize?: number } }).voiceTest.recordedSize)).toBeUndefined();
  });

  test("captures mixed Telugu-English speech, sends PCM WAV, and supports voice reply playback controls", async ({ page }) => {
    await mockVoiceBrowser(page);
    await expect(page.getByRole("button", { name: "Start microphone recording" })).toBeVisible();
    expect(await page.evaluate(() => (window as Window & { voiceTest: { micCalls: number } }).voiceTest.micCalls)).toBe(0);

    await startRecording(page);
    await expect(page.getByRole("button", { name: "Stop recording" })).toBeVisible();
    await stopRecording(page);
    await page.getByRole("button", { name: "Send reviewed recording to Prisma" }).click();
    await expect(page.getByLabel("Prisma transcript or typed message")).toHaveValue(transcript);
    const recorded = await page.evaluate(() => (window as Window & { voiceTest: { micCalls: number; tracksStopped: number; recordedFormat?: string; recordedSize?: number; isPcmWav?: boolean } }).voiceTest);
    expect(recorded.micCalls).toBe(1);
    expect(recorded.tracksStopped).toBe(1);
    expect(recorded.recordedFormat).toContain("multipart/form-data");
    expect(recorded.recordedSize).toBeGreaterThan(44);
    expect(recorded.isPcmWav).toBe(true);

    await page.getByRole("button", { name: /Send to tutor/ }).click();
    await expect(page.getByText(reply.reply)).toBeVisible();
    await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
    const audio = page.locator(".vt-playback audio");
    await expect(audio).toBeVisible();
    await expect.poll(() => audio.evaluate(element => element.currentTime)).toBeGreaterThan(0.1);
    await audio.evaluate(element => element.pause());
    await expect.poll(() => audio.evaluate(element => element.paused)).toBe(true);
    await audio.evaluate(element => { void element.play(); });
    await expect.poll(() => audio.evaluate(element => element.currentTime)).toBeGreaterThan(0.2);
    await page.getByRole("button", { name: "Stop audio" }).click();
    await expect.poll(() => audio.evaluate(element => element.paused)).toBe(true);
    await expect.poll(() => audio.evaluate(element => element.currentTime)).toBe(0);
  });

  test("Open Notepad is planned locally and requires both approvals and a verified window", async ({ page }) => {
    const requests: string[] = [];
    const proposed = { action: "open_app", app_id: "notepad" };
    const origin = "http://127.0.0.1:18765";
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
    };
    let nativeApproved = false;
    let verifyExecution = false;
    let delayActivation = false;
    let releaseActivation!: () => void;
    const activationHeld = new Promise<void>(resolve => { releaseActivation = resolve; });
    let stopRequests = 0;
    await page.route(`${origin}/**`, async route => {
      const request = route.request();
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const path = new URL(request.url()).pathname;
      switch (path) {
        case "/pair": return route.fulfill({ headers: cors, json: { token: "mock-pairing" } });
        case "/health": return route.fulfill({ headers: cors, json: { active: true } });
        case "/disable":
          requests.push("disable");
          return route.fulfill({ headers: cors, json: { active: false } });
        case "/activate":
          if (delayActivation) await activationHeld;
          return route.fulfill({ headers: cors, json: { active: true } });
        case "/desktop/snapshot":
          requests.push("snapshot");
          return route.fulfill({ headers: cors, status: 503, json: { error: "Window inventory unavailable." } });
        case "/desktop/confirm":
          requests.push("confirm");
          expect(request.postDataJSON().action).toEqual(proposed);
          return route.fulfill(nativeApproved
            ? { headers: cors, json: { confirmation_token: "mock-one-use-ticket" } }
            : { headers: cors, status: 403, json: { error: "Local Windows operator declined." } });
        case "/desktop/execute":
          requests.push("execute");
          expect(request.postDataJSON()).toMatchObject({ action: proposed, confirmation_token: "mock-one-use-ticket" });
          return route.fulfill({ headers: cors, json: verifyExecution ? { ok: true, action: "open_app", app_id: "notepad", verified_window: "mock-window" } : { ok: true, action: "open_app", app_id: "notepad" } });
        case "/stop":
          stopRequests += 1;
          return route.fulfill({ headers: cors, json: { active: false } });
        default: return route.abort();
      }
    });
    await page.route("**/api/v1/assistant/voice/speech", route => route.fulfill({ status: 204 }));
    await page.route("**/api/v1/assistant/desktop/interpret", route => {
      requests.push("interpret");
      expect(route.request().postDataJSON().transcript).toBe("Open Notepad");
      return route.fulfill({ json: { action: proposed } });
    });
    await mockVoiceBrowser(page, { transcript: "Open Notepad." });
    await startRecording(page);
    await stopRecording(page);
    await page.getByRole("button", { name: "Send reviewed recording to Prisma" }).click();
    await expect(page.getByLabel("Prisma transcript or typed message")).toHaveValue("Open Notepad.");

    const panel = page.getByRole("region", { name: "Windows desktop control" });
    const interpret = panel.getByRole("button", { name: "Prepare Notepad action" });
    const confirm = panel.getByRole("button", { name: "Confirm and execute" });
    await panel.getByRole("button", { name: "Connect to local companion" }).click();
    await expect(panel.getByRole("status")).toContainText("Connected · control disabled");
    expect(requests.splice(0)).toEqual(["disable"]);
    await panel.getByRole("button", { name: "Enable control" }).click();
    await expect(interpret).toBeDisabled();
    expect(requests).toEqual([]);
    await panel.getByRole("button", { name: "I reviewed this transcript" }).click();
    await expect(interpret).toBeEnabled();
    expect(requests).toEqual([]);
    await interpret.click();
    await expect(confirm).toBeVisible();
    expect(requests).toEqual([]);

    await confirm.click();
    await expect(panel.getByText("Local Windows operator declined.", { exact: false })).toBeVisible();
    expect(requests).toEqual(["confirm"]);
    await expect(panel.getByText("completed open_app", { exact: false })).toHaveCount(0);

    nativeApproved = true;
    await interpret.click();
    await confirm.click();
    await expect(panel.getByRole("status")).toContainText("The companion did not confirm the approved action result.");
    await expect(panel.getByText("completed open_app", { exact: false })).toHaveCount(0);
    verifyExecution = true;
    await interpret.click();
    await confirm.click();
    await expect(panel.getByRole("status")).toContainText("Completed: completed open_app");
    expect(requests).toEqual(["confirm", "confirm", "execute", "confirm", "execute"]);
    await panel.getByRole("button", { name: "Emergency Stop" }).click();
    await expect(interpret).toBeDisabled();
    await expect(confirm).toHaveCount(0);

    delayActivation = true;
    const activating = page.waitForRequest(`${origin}/activate`);
    await panel.getByRole("button", { name: "Enable control" }).click();
    await activating;
    await panel.getByRole("button", { name: "Emergency Stop" }).click();
    await expect.poll(() => stopRequests).toBe(2);
    releaseActivation();
    await expect.poll(() => stopRequests).toBe(3);
    await expect(panel.getByRole("button", { name: "Enable control" })).toBeEnabled();
    await expect(confirm).toHaveCount(0);
  });

  test("approved link previews its exact URL and unknown links never reach the companion", async ({ page }) => {
    const origin = "http://127.0.0.1:18765";
    const requests: string[] = [];
    let dropExecutionResponse = false;
    const action = { action: "open_named_link", url: "https://www.youtube.com/" };
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
    };
    await page.route(`${origin}/**`, async route => {
      const request = route.request();
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
      const path = new URL(request.url()).pathname;
      if (path === "/pair") return route.fulfill({ headers: cors, json: { token: "mock-pairing" } });
      if (path === "/health") return route.fulfill({ headers: cors, json: { active: false } });
      if (path === "/activate") return route.fulfill({ headers: cors, json: { active: true } });
      requests.push(path);
      if (path === "/desktop/confirm") {
        expect(request.postDataJSON().action).toEqual(action);
        return route.fulfill({ headers: cors, json: { confirmation_token: "mock-link-ticket" } });
      }
      if (path === "/desktop/execute") {
        expect(request.postDataJSON()).toMatchObject({ action, confirmation_token: "mock-link-ticket" });
        if (dropExecutionResponse) return route.abort();
        return route.fulfill({ headers: cors, json: { ok: true, ...action } });
      }
      return route.abort();
    });
    await page.route("**/api/v1/assistant/voice/speech", route => route.fulfill({ status: 204 }));
    await page.route("**/api/v1/assistant/desktop/interpret", route => {
      requests.push("gemini");
      return route.abort();
    });
    await mockVoiceBrowser(page, { transcript: "Open You Tube." });
    await startRecording(page);
    await stopRecording(page);
    await page.getByRole("button", { name: "Send reviewed recording to Prisma" }).click();
    const transcriptBox = page.getByLabel("Prisma transcript or typed message");
    await expect(transcriptBox).toHaveValue("Open You Tube.");
    const panel = page.getByRole("region", { name: "Windows desktop control" });
    const prepare = panel.getByRole("button", { name: "Prepare link action" });
    const confirm = panel.getByRole("button", { name: "Confirm and execute" });
    await panel.getByRole("button", { name: "Connect to local companion" }).click();
    await panel.getByRole("button", { name: "Enable control" }).click();
    await expect(prepare).toBeDisabled();
    await panel.getByRole("button", { name: "I reviewed this transcript" }).click();
    await prepare.click();
    await expect(panel.getByText("open https://www.youtube.com/", { exact: true })).toBeVisible();
    expect(requests).toEqual([]);
    await transcriptBox.fill("Open the website Example.");
    await expect(confirm).toHaveCount(0);
    await panel.getByRole("button", { name: "I reviewed this transcript" }).click();
    await prepare.click();
    await expect(panel.getByRole("status", { name: "Clarification needed" })).toContainText("Choose an approved link");
    await expect(confirm).toHaveCount(0);
    expect(requests).toEqual([]);

    await transcriptBox.fill("Open You Tube.");
    await panel.getByRole("button", { name: "I reviewed this transcript" }).click();
    await prepare.click();
    dropExecutionResponse = true;
    await confirm.click();
    await expect(panel.getByRole("status")).toContainText("Check whether the link opened before retrying");
    await expect(confirm).toHaveCount(0);
    expect(requests.splice(0)).toEqual(["/desktop/confirm", "/desktop/execute"]);

    dropExecutionResponse = false;
    await prepare.click();
    await confirm.click();
    await expect(panel.getByRole("status")).toContainText("sent https://www.youtube.com/ to the default browser");
    expect(requests).toEqual(["/desktop/confirm", "/desktop/execute"]);
  });

  test("mic denial and Prisma errors keep typed fallback available with visible errors", async ({ page }) => {
    await mockVoiceBrowser(page, { micDenied: true });
    await startRecording(page);
    await expect(page.getByRole("alert")).toContainText("Microphone access was denied");
    await expect(page.getByLabel("Prisma transcript or typed message")).toBeEnabled();

    const prismaPage = await page.context().newPage();
    await mockVoiceBrowser(prismaPage, { sttStatus: 503 });
    await startRecording(prismaPage);
    await expect(prismaPage.getByRole("button", { name: "Stop recording" })).toBeVisible();
    await stopRecording(prismaPage);
    await prismaPage.getByRole("button", { name: "Send reviewed recording to Prisma" }).click();
    await expect(prismaPage.getByRole("alert")).toContainText("Mock Prisma unavailable.");
    await expect(prismaPage.getByLabel("Prisma transcript or typed message")).toBeEnabled();
    await expect(prismaPage.getByRole("button", { name: "Send reviewed recording to Prisma" })).toBeEnabled();
    await prismaPage.close();
  });

  test("Timbre failure leaves tutor text available and offers a clearly labeled local tone", async ({ page }) => {
    await mockVoiceBrowser(page, { ttsStatus: 503 });
    await page.getByLabel("Prisma transcript or typed message").fill("Explain fractions.");
    await page.getByRole("button", { name: /Send to tutor/ }).click();
    await expect(page.getByText(reply.reply)).toBeVisible();
    await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
    await expect(page.getByText(/Speech playback failed/)).toBeVisible();
    await page.getByRole("button", { name: "Play local demo tone" }).click();
    await expect(page.getByText(/not generated speech/)).toBeVisible();
  });
});
