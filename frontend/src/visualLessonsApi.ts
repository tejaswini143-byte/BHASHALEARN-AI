import { ApiError, request } from "./auth";
import { validateGeneratedVisualLessonEnvelope, validateVisualLessonEnvelope, type GeneratedVisualLessonEnvelope, type VisualLessonEnvelope } from "./visualLessonContract";
import type { VisualLesson, VisualLessonId } from "./visualLessonsModel";

/** Only authenticated, validated, allowlisted scenes are eligible for rendering. */
export async function fetchVisualLessonCatalog(token: string, signal?: AbortSignal): Promise<VisualLesson[]> {
  const response = await request<unknown>("/visual-lessons", {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  if (!Array.isArray(response) || response.length === 0 || response.length > 3) {
    throw new Error("Invalid visual lesson catalog.");
  }
  const envelopes: VisualLessonEnvelope[] = response.map(validateVisualLessonEnvelope);
  if (new Set(envelopes.map(item => item.lesson.id)).size !== envelopes.length) {
    throw new Error("Duplicate visual lesson IDs.");
  }
  return envelopes.map(item => item.lesson);
}

export function visualLessonApiError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "Your session has expired. Please sign in again.";
  if (error instanceof Error && error.name === "AbortError") return "";
  return "Live lesson catalog unavailable. Showing built-in lessons.";
}

export async function generateVisualLesson(token: string, sessionId: string, topic: string, sceneKind: VisualLessonId, language: "english" | "telugu"): Promise<GeneratedVisualLessonEnvelope> {
  const response = await request<unknown>("/visual-lessons/generate", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ topic, scene_kind: sceneKind, language, session_id: sessionId }),
  });
  const generated = validateGeneratedVisualLessonEnvelope(response);
  // Keep the API type narrow while returning the strictly validated v2 envelope.
  return generated as GeneratedVisualLessonEnvelope;
}
