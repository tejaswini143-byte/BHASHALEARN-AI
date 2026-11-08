import { expect, test, type Page } from "@playwright/test";

const session = { id: "voice-session-10c", topic: "Equivalent fractions", language: "mixed", created_at: "2026-11-08T10:00:00Z" };
const prefs = { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null };
const reply = { id: "assistant-1", role: "assistant", content: "\\u0C28\\u0C2E\\u0C38\\u0C4D\\u0C15\\u0C3E\\u0C30\\u0C02! Fractions show equal parts.", created_at: "2026-11-08T10:01:00Z" };

function wave(): Buffer {
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

async function openImmersiveVoice(page: Page, localDemo = false) {
  await page.addInitScript(() => {
    sessionStorage.setItem("bhashalearn_access_token", "int10c-browser-token");
    (window as Window & { micAccessCalls?: number }).micAccessCalls = 0;
    Object.defineProperty(window, "AudioContext", { configurable: true, value: undefined });
    const media = navigator.mediaDevices;
    if (media?.getUserMedia) {
      const original = media.getUserMedia.bind(media);
      Object.defineProperty(media, "getUserMedia", { configurable: true, value: (...args: Parameters<typeof original>) => {
        (window as Window & { micAccessCalls?: number }).micAccessCalls! += 1;
        return original(...args);
      } });
    }
    const proto = HTMLMediaElement.prototype;
    const nativePlay = proto.play;
    const nativePause = proto.pause;
    proto.play = function(this: HTMLMediaElement) {
      const audio = this as HTMLMediaElement & { __clock?: number; __paused?: boolean; __ended?: boolean; __timer?: number };
      if (!audio.src.startsWith("blob:")) return nativePlay.call(this);
      if (audio.__timer) window.clearInterval(audio.__timer);
      audio.__clock ??= 0; audio.__paused = false; audio.__ended = false;
      Object.defineProperty(audio, "currentTime", { configurable: true, get: () => audio.__clock, set: value => { audio.__clock = Number(value) || 0; audio.__ended = false; } });
      Object.defineProperty(audio, "duration", { configurable: true, get: () => 8 });
      Object.defineProperty(audio, "paused", { configurable: true, get: () => audio.__paused });
      Object.defineProperty(audio, "ended", { configurable: true, get: () => audio.__ended });
      audio.dispatchEvent(new Event("play"));
      audio.__timer = window.setInterval(() => {
        if (audio.__paused) return;
        audio.__clock = (audio.__clock || 0) + 0.04;
        audio.dispatchEvent(new Event("timeupdate"));
        if (audio.__clock >= 8) {
          audio.__ended = true; audio.__paused = true; window.clearInterval(audio.__timer);
          audio.dispatchEvent(new Event("ended"));
        }
      }, 40);
      return Promise.resolve();
    };
    proto.pause = function(this: HTMLMediaElement) {
      const audio = this as HTMLMediaElement & { __paused?: boolean; __timer?: number };
      if (!audio.src.startsWith("blob:")) return nativePause.call(this);
      if (audio.__paused === false) { audio.__paused = true; audio.dispatchEvent(new Event("pause")); }
    };
  });
  await page.route("**/api/v1/auth/me", route => localDemo ? route.abort() : route.fulfill({ json: { id: "student-10c", email: "learner@example.test", display_name: "Voice Learner" } }));
  await page.route("**/api/v1/sessions?limit=100", route => localDemo ? route.abort() : route.fulfill({ json: [session] }));
  await page.route("**/api/v1/students/me/preferences", route => localDemo ? route.abort() : route.fulfill({ json: prefs }));
  await page.route("**/api/v1/sessions/voice-session-10c/context?limit=500", route => route.fulfill({ json: {
    session_id: session.id, topic: session.topic, preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null,
    messages: [reply], visual_lesson: null,
  } }));
  if (!localDemo) await page.route("**/api/v1/voice/sessions/voice-session-10c/speech", route => route.fulfill({ status: 200, contentType: "audio/wav", body: wave() }));
  await page.goto("/immersive");
  await expect(page.getByRole("heading", { name: "The Pythagorean theorem" })).toBeVisible();
  expect(await page.evaluate(() => (window as Window & { micAccessCalls?: number }).micAccessCalls)).toBe(0);
  await page.getByRole("button", { name: "Open voice tutor" }).click();
  await expect(page.getByRole("heading", { name: localDemo ? "Voice synchronization demo" : "Equivalent fractions" })).toBeVisible();
  if (!localDemo) await expect(page.getByText("Fractions show equal parts.")).toBeVisible();
}

test("immersive tutor speech follows playback, pause, resume, replay, interruption, and cleanup", async ({ page }) => {
  await openImmersiveVoice(page);
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  const audio = page.locator(".vt-playback audio");
  await expect(audio).toBeVisible();
  await expect.poll(() => audio.evaluate(element => element.currentTime)).toBeGreaterThan(0.15);
  await expect(page.locator(".vt-playback small")).not.toContainText("sil mouth shape");

  await audio.evaluate(element => element.pause());
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Paused");
  await expect(page.locator(".vt-playback small")).toContainText("sil mouth shape");
  await audio.evaluate(element => { void element.play(); });
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");

  const beforeReplay = await audio.evaluate(element => element.currentTime);
  const previousAudio = await audio.elementHandle();
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect.poll(() => audio.evaluate(element => element.currentTime)).toBeLessThan(beforeReplay);
  await expect.poll(() => previousAudio!.evaluate(element => element.isConnected)).toBe(false);
  await previousAudio!.evaluate(element => element.dispatchEvent(new Event("ended")));
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  await page.getByRole("button", { name: "Stop audio" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speech interrupted");
  await expect(audio).toHaveJSProperty("paused", true);

  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  await page.getByRole("button", { name: "Close voice tutor" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Voice ready - no audio");
  expect(await audio.count()).toBe(0);
});

test("immersive tutor shows an explicit unavailable state when speech generation fails", async ({ page }) => {
  await openImmersiveVoice(page);
  await page.unroute("**/api/v1/voice/sessions/voice-session-10c/speech");
  await page.route("**/api/v1/voice/sessions/voice-session-10c/speech", route => route.fulfill({ status: 503, json: { detail: "Gnani Timbre is not configured." } }));
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Voice unavailable");
  await expect(page.locator(".vt-notice")).toContainText("Speech playback failed");
  await page.getByRole("button", { name: "Play local demo tone" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  await expect(page.locator(".vt-notice")).toContainText("not generated speech");
});


test("audio completion returns the teacher to idle and route changes stop playback", async ({ page }) => {
  await openImmersiveVoice(page);
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  const audio = page.locator(".vt-playback audio");
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  await audio.evaluate(element => { element.currentTime = 7.96; });
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Voice ready - no audio");
  await expect(page.locator(".vt-playback small")).toContainText("sil mouth shape");

  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  await page.getByRole("link", { name: "Exit classroom" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.locator(".vt-playback audio")).toHaveCount(0);
});

test("reduced motion preserves voice playback state and media-clock updates", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openImmersiveVoice(page);
  await expect(page.getByLabel("Reduce motion")).toBeChecked();
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  await expect.poll(() => page.locator(".vt-playback audio").evaluate(element => element.currentTime)).toBeGreaterThan(0.15);
  await expect(page.getByLabel("Reduce motion")).toBeChecked();
  await page.getByRole("button", { name: "Stop audio" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speech interrupted");
});

test("invalid or missing WAV response reports voice unavailable", async ({ page }) => {
  await openImmersiveVoice(page);
  await page.unroute("**/api/v1/voice/sessions/voice-session-10c/speech");
  await page.route("**/api/v1/voice/sessions/voice-session-10c/speech", route => route.fulfill({ status: 200, contentType: "text/plain", body: "no audio" }));
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Voice unavailable");
  await expect(page.locator(".vt-notice")).toContainText("unsupported audio format");
});


test("backend outage offers a labeled local tone demo without microphone or speech API calls", async ({ page }) => {
  await openImmersiveVoice(page, true);
  await expect(page.getByText("LOCAL DEMO - BACKEND UNAVAILABLE")).toBeVisible();
  await expect(page.getByText("LOCAL DEMO - NO GNANI AUDIO")).toBeVisible();
  await expect(page.getByText(/generated tone demonstrates avatar timing only/)).toBeVisible();
  expect(await page.evaluate(() => (window as Window & { micAccessCalls?: number }).micAccessCalls)).toBe(0);
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  await expect(page.getByTestId("immersive-voice-state")).toHaveText("Speaking");
  await expect(page.locator(".vt-notice")).toContainText("not generated speech");
  await page.getByLabel("Prisma transcript or typed message").fill("What is a fraction?");
  await page.getByRole("button", { name: "Send to tutor" }).click();
  await expect(page.getByText(/no backend was contacted/)).toBeVisible();
});
