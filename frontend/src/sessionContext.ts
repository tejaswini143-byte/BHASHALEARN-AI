import { getToken, request } from "./auth";
import type { LearningPace } from "./learningPreferences";

export type LearningLanguage = "english" | "telugu" | "mixed";
export type LearningLevel = "beginner" | "intermediate" | "advanced";
export type SharedMessage = { id: string; role: "user" | "assistant"; content: string; created_at: string };
export type VisualLessonContext = {
  visual_key: string;
  title: string;
  concept: string;
  description: string;
  start_node: string | null;
  end_node: string | null;
  updated_at: string;
};
export type SharedSessionContext = {
  session_id: string;
  topic: string;
  preferred_language: LearningLanguage;
  learning_level: LearningLevel;
  learning_pace: LearningPace;
  learning_goal: string | null;
  messages: SharedMessage[];
  visual_lesson: VisualLessonContext | null;
};

export function sessionHeaders() {
  return { Authorization: "Bearer " + getToken() };
}

export function getSharedSessionContext(sessionId: string): Promise<SharedSessionContext> {
  return request<SharedSessionContext>(`/sessions/${encodeURIComponent(sessionId)}/context?limit=500`, { headers: sessionHeaders() });
}
