import type { LessonPlan } from "./lessonEngine";

export type CameraPreset = "overview" | "teacher" | "lesson";
export const cameraPresets: Record<CameraPreset, { position: [number, number, number]; target: [number, number, number]; label: string }> = {
  overview: { position: [0, 2.4, 10.5], target: [0, 1.45, -2], label: "Overview" },
  teacher: { position: [-2.9, 2.2, 7.6], target: [-1.5, 1.45, -1.2], label: "Teacher" },
  lesson: { position: [3.1, 2.5, 7.4], target: [1.15, 1.9, -1.8], label: "Lesson" },
};

export function focusedLessonObjectIds(lesson: LessonPlan, stepIndex: number): string[] {
  if (stepIndex < 0 || stepIndex >= lesson.steps.length) return [];
  return [...new Set(lesson.steps[stepIndex].commands.flatMap(command =>
    command.type === "highlight" || command.type === "focus" ? [command.id] :
      command.type === "annotate" || command.type === "draw" ? [command.object.id] : [],
  ))];
}
