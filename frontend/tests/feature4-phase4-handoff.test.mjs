import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const visual = readFileSync(new URL("../src/VisualLessons.tsx", import.meta.url), "utf8");
const immersive = readFileSync(new URL("../src/ImmersiveClassroom.tsx", import.meta.url), "utf8");
const voice = readFileSync(new URL("../src/VoiceTutor.tsx", import.meta.url), "utf8");

test("visual lesson links preserve allowlisted lesson context", () => {
  assert.match(visual, /encodeURIComponent\(controls.lessonId\)/);
  assert.match(visual, /to=\{immersiveUrl\}/);
  assert.match(visual, /to=\{voiceUrl\}/);
});
test("immersive board chooses a matching lesson and resets playback", () => {
  assert.match(immersive, /searchParams.get\("lesson"\)/);
  assert.match(immersive, /requestedLesson === "geometry" \? "pythagoras"/);
  assert.match(immersive, /setPlayback\(\{ step: -1, playing: false \}\)/);
});
test("voice tutor prefills requested lesson topic without auto-creating sessions", () => {
  assert.match(voice, /params.get\("topic"\)/);
  assert.match(voice, /slice\(0, 200\)/);
});
