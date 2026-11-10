import { expect, test } from "@playwright/test";

const session = { id: "int20-session", topic: "Fractions", language: "mixed", created_at: "2026-11-08T10:00:00Z" };
const prefs = { preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null };
const initialMessages = [{ id: "assistant-1", role: "assistant", content: "A fraction has a numerator and denominator.", created_at: "2026-11-08T10:01:00Z" }];

function wav(): Buffer {
  const rate = 16000;
  const samples = rate * 5;
  const bytes = Buffer.alloc(44 + samples * 2);
  bytes.write("RIFF", 0); bytes.writeUInt32LE(bytes.length - 8, 4); bytes.write("WAVE", 8);
  bytes.write("fmt ", 12); bytes.writeUInt32LE(16, 16); bytes.writeUInt16LE(1, 20); bytes.writeUInt16LE(1, 22);
  bytes.writeUInt32LE(rate, 24); bytes.writeUInt32LE(rate * 2, 28); bytes.writeUInt16LE(2, 32); bytes.writeUInt16LE(16, 34);
  bytes.write("data", 36); bytes.writeUInt32LE(samples * 2, 40);
  for (let i = 0; i < samples; i += 1) bytes.writeInt16LE(Math.round(Math.sin(i * 2 * Math.PI * 220 / rate) * 4000), 44 + i * 2);
  return bytes;
}

test("student switches language, interrupts speech, asks a contextual question, and confirms resume", async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("bhashalearn_access_token", "int20-e2e-token");
    const proto = HTMLMediaElement.prototype;
    proto.play = function(this: HTMLMediaElement) {
      const audio = this as HTMLMediaElement & { __clock?: number; __paused?: boolean; __ended?: boolean; __timer?: number };
      if (!audio.src.startsWith("blob:")) return Promise.resolve();
      if (audio.__timer) window.clearInterval(audio.__timer);
      audio.__clock ??= 0; audio.__paused = false; audio.__ended = false;
      Object.defineProperty(audio, "currentTime", { configurable: true, get: () => audio.__clock, set: value => { audio.__clock = Number(value) || 0; audio.__ended = false; } });
      Object.defineProperty(audio, "paused", { configurable: true, get: () => audio.__paused });
      Object.defineProperty(audio, "ended", { configurable: true, get: () => audio.__ended });
      audio.dispatchEvent(new Event("play"));
      audio.__timer = window.setInterval(() => {
        if (audio.__paused) return;
        audio.__clock = (audio.__clock || 0) + 0.04;
        if (audio.__clock >= 5) { audio.__ended = true; audio.__paused = true; window.clearInterval(audio.__timer); audio.dispatchEvent(new Event("ended")); }
      }, 40);
      return Promise.resolve();
    };
    proto.pause = function(this: HTMLMediaElement) {
      const audio = this as HTMLMediaElement & { __paused?: boolean };
      if (audio.src.startsWith("blob:")) { audio.__paused = true; audio.dispatchEvent(new Event("pause")); }
    };
  });
  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: { id: "student-int20", email: "learner@example.test", display_name: "Voice Learner" } }));
  await page.route("**/api/v1/sessions?limit=100", route => route.fulfill({ json: [session] }));
  await page.route("**/api/v1/students/me/preferences", async route => {
    if (route.request().method() === "PUT") return route.fulfill({ json: { ...prefs, ...route.request().postDataJSON() } });
    return route.fulfill({ json: prefs });
  });
  await page.route("**/api/v1/sessions/int20-session/context?limit=500", route => route.fulfill({ json: {
    session_id: session.id, topic: session.topic, preferred_language: "mixed", learning_level: "beginner", learning_pace: "steady", learning_goal: null,
    messages: initialMessages, visual_lesson: null,
  } }));
  let state: Record<string, unknown> = {
    session_id: session.id, topic: session.topic, lesson_step: "fractions:equal-parts", student_question: null,
    active_response_language: "mixed", playback_state: "idle", voice_transcript: null,
    checkpoint_message_id: null, checkpoint_playback_ms: null, resume_status: "none",
  };
  await page.route("**/api/v1/voice/sessions/provider-mode", route => route.fulfill({ json: { mode: "unavailable", configured: false } }));
  await page.route("**/api/v1/voice/sessions/int20-session/state", async route => {
    if (route.request().method() === "PUT") state = { ...state, ...route.request().postDataJSON() };
    return route.fulfill({ json: state });
  });
  let chatPayload: Record<string, unknown> | null = null;
  await page.route("**/api/v1/tutor/sessions/int20-session/chat", async route => {
    chatPayload = route.request().postDataJSON();
    return route.fulfill({ json: { session_id: session.id, reply: "The denominator tells how many equal parts make the whole.", language: "english", learning_level: "beginner", citations: [], grounded: false, retrieval_used: false } });
  });
  await page.route("**/api/v1/sessions/int20-session/messages?limit=500", route => route.fulfill({ json: [
    ...initialMessages,
    { id: "user-2", role: "user", content: "What does denominator mean?", created_at: "2026-11-08T10:02:00Z" },
    { id: "assistant-2", role: "assistant", content: "The denominator tells how many equal parts make the whole.", created_at: "2026-11-08T10:03:00Z" },
  ] }));
  await page.route("**/api/v1/voice/sessions/int20-session/speech", route => route.fulfill({ status: 200, contentType: "audio/wav", body: wav() }));

  await page.goto("/voice?session=int20-session");
  await expect(page.getByRole("heading", { name: "Fractions" })).toBeVisible();
  await expect(page.getByText("GNANI UNAVAILABLE · TEXT CLASSROOM AVAILABLE")).toBeVisible();
  await page.getByRole("button", { name: "Generate or replay tutor speech" }).click();
  const audio = page.locator(".vt-playback audio");
  await expect.poll(() => audio.evaluate(element => element.currentTime)).toBeGreaterThan(0.2);
  await page.getByLabel("Tutor language").selectOption("english");
  await page.getByRole("button", { name: "Interrupt tutor speech" }).click();
  await expect(page.getByRole("group", { name: "Lesson continuation" })).toContainText("lesson is paused");
  await audio.evaluate(element => { element.dispatchEvent(new Event("ended")); element.dispatchEvent(new Event("play")); });
  await expect(page.getByRole("group", { name: "Lesson continuation" })).toBeVisible();
  await page.getByLabel("Prisma transcript or typed message").fill("What does denominator mean?");
  await page.getByRole("button", { name: /Send to tutor/ }).click();
  await expect(page.getByText("The denominator tells how many equal parts make the whole.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Resume lesson" })).toBeVisible();
  expect(chatPayload).toMatchObject({ message: "What does denominator mean?", language: "english" });
  expect(state).toMatchObject({ active_response_language: "english", resume_status: "awaiting_confirmation", checkpoint_message_id: "assistant-1" });

  await page.getByRole("button", { name: "Resume lesson" }).click();
  await expect.poll(() => audio.evaluate(element => element.currentTime)).toBeGreaterThan(1.2);
  await expect(page.getByText("Your question was answered. The lesson is paused at 0 seconds.")).toHaveCount(0);
});
