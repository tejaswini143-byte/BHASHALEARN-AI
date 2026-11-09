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

async function mockVoiceBrowser(page: Page, options: { micDenied?: boolean; sttStatus?: number; ttsStatus?: number } = {}) {
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
          onaudioprocess: null, connect: () => undefined, disconnect: () => undefined,
        };
        window.setTimeout(() => processor.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array(4096).fill(0.15) } }), 10);
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
  await page.route("**/api/v1/students/me/preferences", route => route.fulfill({ json: prefs }));
  await page.route(`**/api/v1/sessions/${session.id}/context?limit=500`, route => route.fulfill({ json: {
    session_id: session.id, topic: session.topic, preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null,
    messages: [], visual_lesson: null,
  } }));
  await page.route(`**/api/v1/sessions/${session.id}/messages?limit=500`, route => route.fulfill({ json: [
    { id: "user-mock", role: "user", content: transcript, created_at: "2026-11-09T10:01:00Z" },
    { id: "assistant-mock", role: "assistant", content: reply.reply, created_at: "2026-11-09T10:02:00Z" },
  ] }));
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
      : { json: { session_id: session.id, transcript, detected_language: "te+en", language_mode: "mixed" } });
  });
  await page.route(`**/api/v1/tutor/sessions/${session.id}/chat`, route => route.fulfill({ json: reply }));
  await page.route(`**/api/v1/voice/sessions/${session.id}/speech`, route => options.ttsStatus && options.ttsStatus !== 200
    ? route.fulfill({ status: options.ttsStatus, json: { detail: "Mock Timbre unavailable." } })
    : route.fulfill({ status: 200, contentType: "audio/wav", body: pcmWav() }));
  await page.goto("/voice");
  await expect(page.getByRole("heading", { name: "Fractions" })).toBeVisible();
}

test.describe("Mocked Gnani voice classroom (no live provider calls)", () => {
  test("captures mixed Telugu-English speech, sends PCM WAV, and supports voice reply playback controls", async ({ page }) => {
    await mockVoiceBrowser(page);
    await expect(page.getByRole("button", { name: "Start microphone recording" })).toBeVisible();
    expect(await page.evaluate(() => (window as Window & { voiceTest: { micCalls: number } }).voiceTest.micCalls)).toBe(0);

    await page.getByRole("button", { name: "Start microphone recording" }).evaluate(button => (button as HTMLButtonElement).click());
    await expect(page.getByRole("button", { name: "Stop recording" })).toBeVisible();
    await page.getByRole("button", { name: "Stop recording" }).evaluate(button => (button as HTMLButtonElement).click());
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

  test("mic denial and Prisma errors keep typed fallback available with visible errors", async ({ page }) => {
    await mockVoiceBrowser(page, { micDenied: true });
    await page.getByRole("button", { name: "Start microphone recording" }).evaluate(button => (button as HTMLButtonElement).click());
    await expect(page.getByRole("alert")).toContainText("Microphone access was denied");
    await expect(page.getByLabel("Prisma transcript or typed message")).toBeEnabled();

    const prismaPage = await page.context().newPage();
    await mockVoiceBrowser(prismaPage, { sttStatus: 503 });
    await prismaPage.getByRole("button", { name: "Start microphone recording" }).evaluate(button => (button as HTMLButtonElement).click());
    await expect(prismaPage.getByRole("button", { name: "Stop recording" })).toBeVisible();
    await prismaPage.getByRole("button", { name: "Stop recording" }).evaluate(button => (button as HTMLButtonElement).click());
    await expect(prismaPage.getByRole("alert")).toContainText("Mock Prisma unavailable.");
    await expect(prismaPage.getByLabel("Prisma transcript or typed message")).toBeEnabled();
    await prismaPage.close();
  });

  test("Timbre failure leaves tutor text available and offers a clearly labeled local tone", async ({ page }) => {
    await mockVoiceBrowser(page, { ttsStatus: 503 });
    await page.getByLabel("Prisma transcript or typed message").fill("Explain fractions.");
    await page.getByRole("button", { name: /Send to tutor/ }).click();
    await expect(page.getByText(reply.reply)).toBeVisible();
    await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
    await expect(page.locator(".vt-notice")).toContainText("Speech playback failed");
    await page.getByRole("button", { name: "Play local demo tone" }).click();
    await expect(page.locator(".vt-notice")).toContainText("not generated speech");
  });
});
