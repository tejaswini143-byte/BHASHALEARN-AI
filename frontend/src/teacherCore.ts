export type TeacherState = "idle" | "walk" | "turn" | "explain" | "point" | "listen" | "celebrate";
export type Expression = "neutral" | "happy" | "curious" | "encouraging" | "thinking";
export type TeacherMode = "realistic" | "holographic";
export type Viseme = "sil" | "aa" | "ee" | "oh" | "mm" | "fv" | "th";

export type TeacherLessonContext = {
  topic: string;
  preferred_language: "english" | "telugu" | "mixed";
  learning_level: "beginner" | "intermediate" | "advanced";
  learning_goal: string | null;
  visual_lesson: { title: string; concept: string; description: string } | null;
};

export function validateTeacherMode(value: string): TeacherMode {
  if (value === "realistic" || value === "holographic") return value;
  throw new Error("Unknown teacher mode");
}

export function teacherLessonSummary(context: TeacherLessonContext | null): { title: string; detail: string; language: string; level: string } {
  if (!context) return { title: "Lesson context not connected", detail: "Pass the active session ID to share its topic, language, level, and visual lesson.", language: "—", level: "—" };
  const visual = context.visual_lesson;
  return {
    title: visual?.title || context.topic || "Untitled lesson",
    detail: [visual?.concept, visual?.description, context.learning_goal].filter(Boolean).join(" · ") || context.topic,
    language: context.preferred_language,
    level: context.learning_level,
  };
}

export type BoardTarget = { x: number; y: number };
export type TeacherAction =
  | { type: "walkTo"; x: number; z: number }
  | { type: "lookAt"; x: number; y: number; z: number }
  | { type: "pointAt"; target: BoardTarget }
  | { type: "explain"; durationMs?: number }
  | { type: "gesture"; name: "openPalm" | "emphasis" | "wave" }
  | { type: "setExpression"; expression: Expression }
  | { type: "speak"; timeline: VisemeFrame[] };

export type VisemeFrame = { atMs: number; durationMs: number; viseme: Viseme };
export type TeacherSnapshot = { state: TeacherState; expression: Expression; target: BoardTarget | null };

const states = new Set<TeacherState>(["idle", "walk", "turn", "explain", "point", "listen", "celebrate"]);
const expressions = new Set<Expression>(["neutral", "happy", "curious", "encouraging", "thinking"]);
const visemes = new Set<Viseme>(["sil", "aa", "ee", "oh", "mm", "fv", "th"]);

export function transitionTeacher(current: TeacherState, next: TeacherState): TeacherState {
  if (!states.has(current) || !states.has(next)) throw new Error("Unknown teacher state");
  // States are exclusive; every completed transient motion settles back into idle.
  return next;
}

export function settledTeacherState(state: TeacherState): TeacherState {
  return state === "walk" || state === "turn" || state === "point" || state === "explain" || state === "celebrate" ? "idle" : state;
}

export function mapBoardTarget(target: BoardTarget, boardWidth = 6, boardHeight = 3.375): [number, number, number] {
  if (![target.x, target.y, boardWidth, boardHeight].every(Number.isFinite) || target.x < 0 || target.x > 1 || target.y < 0 || target.y > 1 || boardWidth <= 0 || boardHeight <= 0) {
    throw new Error("Board target must be normalized between 0 and 1");
  }
  return [(target.x - 0.5) * boardWidth, (0.5 - target.y) * boardHeight, -4.8];
}

export function validateVisemeTimeline(timeline: VisemeFrame[]): VisemeFrame[] {
  let previousAt = -1;
  for (const frame of timeline) {
    if (!Number.isFinite(frame.atMs) || frame.atMs < 0 || frame.atMs < previousAt || !Number.isFinite(frame.durationMs) || frame.durationMs <= 0 || !visemes.has(frame.viseme)) {
      throw new Error("Invalid viseme timeline");
    }
    previousAt = frame.atMs;
  }
  return timeline.map(frame => ({ ...frame }));
}

export function visemeAt(timeline: VisemeFrame[], timeMs: number): Viseme {
  const frames = validateVisemeTimeline(timeline);
  if (!Number.isFinite(timeMs) || timeMs < 0) return "sil";
  const active = frames.find(frame => timeMs >= frame.atMs && timeMs < frame.atMs + frame.durationMs);
  return active?.viseme ?? "sil";
}

export function validateTeacherAction(action: TeacherAction): TeacherAction {
  if (!action || typeof action !== "object" || !("type" in action)) throw new Error("Invalid teacher action");
  switch (action.type) {
    case "walkTo":
      if (![action.x, action.z].every(Number.isFinite)) throw new Error("walkTo needs finite coordinates");
      break;
    case "lookAt":
      if (![action.x, action.y, action.z].every(Number.isFinite)) throw new Error("lookAt needs finite coordinates");
      break;
    case "pointAt": mapBoardTarget(action.target); break;
    case "explain":
      if (action.durationMs !== undefined && (!Number.isFinite(action.durationMs) || action.durationMs <= 0)) throw new Error("Explain duration must be positive");
      break;
    case "gesture":
      if (!(new Set(["openPalm", "emphasis", "wave"])).has(action.name)) throw new Error("Unknown gesture");
      break;
    case "setExpression":
      if (!expressions.has(action.expression)) throw new Error("Unknown expression");
      break;
    case "speak": validateVisemeTimeline(action.timeline); break;
    default: throw new Error("Unknown teacher action");
  }
  return action;
}

export function createInitialTeacherSnapshot(): TeacherSnapshot {
  return { state: "idle", expression: "neutral", target: null };
}
