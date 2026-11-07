export type BoardShape = "circle" | "rect" | "line" | "triangle" | "text" | "path";
export type LessonObject = {
  id: string;
  shape: BoardShape;
  x: number;
  y: number;
  width?: number;
  height?: number;
  text?: string;
  points?: Array<{ x: number; y: number }>;
  color?: string;
  explanation?: string;
};

export type LessonCommand =
  | { type: "draw" | "annotate"; object: LessonObject }
  | { type: "move"; id: string; x: number; y: number }
  | { type: "highlight" | "focus"; id: string }
  | { type: "erase"; id: string };
export type LessonStep = { title: string; explanation: string; commands: LessonCommand[] };
export type LessonPlan = { id: string; title: string; subject: string; intro: string; objects: LessonObject[]; steps: LessonStep[]; exercise: { prompt: string; choices: string[]; answer: string; feedback: string } };
export type PlaybackState = { step: number; playing: boolean };
export type PlaybackAction = "play" | "pause" | "toggle" | "next" | "previous" | "replay" | "tick" | { type: "go"; step: number; playing?: boolean };
export function playbackReducer(state: PlaybackState, action: PlaybackAction, stepCount: number): PlaybackState {
  if (typeof action === "object") return { step: Math.max(-1, Math.min(action.step, stepCount - 1)), playing: action.playing ?? false };
  if (action === "replay") return { step: -1, playing: false };
  if (action === "pause") return { ...state, playing: false };
  if (action === "play") return { step: state.step >= stepCount - 1 ? -1 : state.step, playing: true };
  if (action === "toggle") return state.playing ? { ...state, playing: false } : { step: state.step >= stepCount - 1 ? -1 : state.step, playing: true };
  if (action === "next") return { step: Math.min(state.step + 1, stepCount - 1), playing: false };
  if (action === "previous") return { step: Math.max(state.step - 1, -1), playing: false };
  return state.step + 1 >= stepCount ? { ...state, playing: false } : { step: state.step + 1, playing: state.playing };
}

const object = (id: string, shape: BoardShape, x: number, y: number, text: string, explanation: string, color = "cyan", width = 160, height = 62): LessonObject => ({ id, shape, x, y, text, explanation, color, width, height });

export const sampleLessons: LessonPlan[] = [
  {
    id: "pythagoras", title: "The Pythagorean theorem", subject: "GEOMETRY · RIGHT TRIANGLES", intro: "Discover how the squares on a right triangle's sides fit together.",
    objects: [
      { id: "triangle", shape: "triangle", x: 280, y: 130, width: 340, height: 280, text: "A", explanation: "A right triangle has one 90° angle.", color: "cyan" },
      object("side-a", "text", 303, 280, "a = 3", "The shorter leg has length 3.", "purple", 115, 48), object("side-b", "text", 455, 385, "b = 4", "The other leg has length 4.", "purple", 115, 48), object("side-c", "text", 485, 225, "c = ?", "The hypotenuse is opposite the right angle.", "gold", 115, 48),
      object("formula", "text", 650, 185, "a² + b² = c²", "This equation relates all three side lengths.", "purple", 245, 62),
    ],
    steps: [
      { title: "Find the right angle", explanation: "The two legs meet at 90°. The side opposite this corner is the hypotenuse.", commands: [{ type: "highlight", id: "triangle" }, { type: "focus", id: "triangle" }] },
      { title: "Square each leg", explanation: "For a = 3 and b = 4: 3² + 4² = 9 + 16 = 25.", commands: [{ type: "highlight", id: "side-a" }, { type: "highlight", id: "side-b" }, { type: "annotate", object: object("sum", "text", 650, 285, "9 + 16 = 25", "Square the legs, then add their areas.", "cyan", 245, 56) }] },
      { title: "Take the square root", explanation: "c² = 25, so c = √25 = 5. A 3–4–5 triangle is a useful check.", commands: [{ type: "highlight", id: "side-c" }, { type: "annotate", object: object("answer", "text", 650, 365, "c = 5", "The hypotenuse has length 5.", "gold", 245, 56) }] },
    ], exercise: { prompt: "If the legs are 5 and 12, what is the hypotenuse?", choices: ["13", "17", "7"], answer: "13", feedback: "5² + 12² = 25 + 144 = 169, and √169 = 13." },
  },
  {
    id: "solar-system", title: "A tour of the solar system", subject: "SPACE · PLANETARY ORDER", intro: "Travel outward from the Sun and notice how the planets are ordered.",
    objects: [object("sun", "circle", 95, 255, "Sun", "Our star sits at the center of the solar system.", "gold", 110, 110), ...[
      ["Mercury", 260, "cyan"], ["Venus", 365, "gold"], ["Earth", 470, "cyan"], ["Mars", 575, "purple"], ["Jupiter", 690, "gold"], ["Saturn", 805, "purple"],
    ].map(([name, x, color], index) => object(String(name).toLowerCase(), "circle", Number(x), 285 + (index % 2) * 36, String(name), `${name} is planet ${index + 1} from the Sun.`, String(color), 64, 64))],
    steps: [
      { title: "Start with the Sun", explanation: "The Sun is a star, not a planet. Its gravity holds the planetary system together.", commands: [{ type: "highlight", id: "sun" }, { type: "focus", id: "sun" }] },
      { title: "The inner planets", explanation: "Mercury, Venus, Earth, and Mars are the four rocky planets nearest the Sun.", commands: ["mercury", "venus", "earth", "mars"].map(id => ({ type: "highlight" as const, id })) },
      { title: "The outer giants", explanation: "Jupiter and Saturn are gas giants. Beyond them are Uranus and Neptune.", commands: [{ type: "highlight", id: "jupiter" }, { type: "highlight", id: "saturn" }, { type: "annotate", object: object("order", "text", 275, 430, "Mercury → Venus → Earth → Mars", "The first four planets, moving outward.", "cyan", 540, 56) }] },
    ], exercise: { prompt: "Which planet comes directly after Earth?", choices: ["Venus", "Mars", "Jupiter"], answer: "Mars", feedback: "Moving outward, the order is Earth, then Mars." },
  },
  {
    id: "vocabulary", title: "Everyday words: Telugu ↔ English", subject: "LANGUAGE · VOCABULARY", intro: "Connect a familiar Telugu word to its English meaning and a spoken example.",
    objects: [object("hello", "rect", 285, 125, "నమస్కారం", "Namaskāram is a polite Telugu greeting.", "cyan", 270, 100), object("meaning", "text", 590, 150, "Hello / Greetings", "This is the English meaning of నమస్కారం.", "purple", 285, 68), object("arrow", "line", 555, 175, "means", "Read from Telugu to its English meaning.", "gold", 58, 6), object("example", "rect", 350, 320, "నమస్కారం! ఎలా ఉన్నారు?", "Namaskāram! Elā unnāru? means Hello! How are you?", "gold", 480, 100)],
    steps: [
      { title: "Say the greeting", explanation: "నమస్కారం (namaskāram) is a respectful way to say hello.", commands: [{ type: "highlight", id: "hello" }, { type: "focus", id: "hello" }] },
      { title: "Connect the meaning", explanation: "It corresponds to “Hello” or “Greetings” in English.", commands: [{ type: "highlight", id: "meaning" }, { type: "focus", id: "meaning" }] },
      { title: "Use it in a sentence", explanation: "నమస్కారం! ఎలా ఉన్నారు? means “Hello! How are you?” Try saying it aloud.", commands: [{ type: "highlight", id: "example" }, { type: "focus", id: "example" }] },
    ], exercise: { prompt: "What does నమస్కారం mean?", choices: ["Thank you", "Hello / Greetings", "Good night"], answer: "Hello / Greetings", feedback: "నమస్కారం (namaskāram) is a polite Telugu greeting." },
  },
];

const validShape = (value: unknown): value is BoardShape => ["circle", "rect", "line", "triangle", "text", "path"].includes(String(value));
export function validateLessonPlan(value: unknown): LessonPlan {
  if (!value || typeof value !== "object") throw new Error("Lesson plan must be an object.");
  const plan = value as Partial<LessonPlan>;
  if (typeof plan.id !== "string" || !plan.id.trim() || typeof plan.title !== "string" || !plan.title.trim() || typeof plan.subject !== "string" || typeof plan.intro !== "string" || !Array.isArray(plan.objects) || !Array.isArray(plan.steps) || plan.steps.length === 0) throw new Error("Lesson plan is missing required fields.");
  const ids = new Set<string>();
  for (const item of plan.objects) {
    if (!item || typeof item.id !== "string" || !item.id || ids.has(item.id) || !validShape(item.shape) || !Number.isFinite(item.x) || !Number.isFinite(item.y) || (item.width !== undefined && (!Number.isFinite(item.width) || item.width <= 0)) || (item.height !== undefined && (!Number.isFinite(item.height) || item.height <= 0)) || (item.text !== undefined && typeof item.text !== "string") || (item.color !== undefined && typeof item.color !== "string") || (item.points !== undefined && (!Array.isArray(item.points) || item.points.some(point => !Number.isFinite(point.x) || !Number.isFinite(point.y)))) ) throw new Error("Lesson objects need unique ids, supported shapes, and finite coordinates.");
    ids.add(item.id);
  }
  for (const step of plan.steps) {
    if (!step || typeof step.title !== "string" || typeof step.explanation !== "string" || !Array.isArray(step.commands)) throw new Error("Each lesson step needs a title, explanation, and command list.");
    for (const command of step.commands) {
      if (!command || typeof command !== "object" || !["draw", "move", "highlight", "annotate", "erase", "focus"].includes(command.type)) throw new Error("Lesson contains an unsupported command.");
      if (command.type === "draw" || command.type === "annotate") {
        const item = command.object;
        if (!item || typeof item.id !== "string" || !validShape(item.shape) || !Number.isFinite(item.x) || !Number.isFinite(item.y)) throw new Error("Draw and annotate commands need a valid object.");
        ids.add(item.id);
      } else if ((command.type === "highlight" || command.type === "focus" || command.type === "erase") && !ids.has(command.id)) throw new Error(`Command references unknown object: ${command.id}`);
      else if (command.type === "move" && (!ids.has(command.id) || !Number.isFinite(command.x) || !Number.isFinite(command.y))) throw new Error("Move commands need a known object and finite coordinates.");
    }
  }
  const exercise = plan.exercise;
  if (!exercise || typeof exercise.prompt !== "string" || !Array.isArray(exercise.choices) || !exercise.choices.length || typeof exercise.answer !== "string" || !exercise.choices.includes(exercise.answer) || typeof exercise.feedback !== "string") throw new Error("Lesson exercise is invalid.");
  return plan as LessonPlan;
}

export type BoardSnapshot = { authored: LessonObject[]; student: LessonObject[]; highlighted: string | null; focused: string | null };
export type BoardState = BoardSnapshot & { undo: BoardSnapshot[]; redo: BoardSnapshot[] };
export type BoardAction =
  | { type: "snapshot" }
  | { type: "set-objects"; authored: LessonObject[] }
  | { type: "replay"; authored: LessonObject[] }
  | { type: "add-student"; object: LessonObject }
  | { type: "update-student"; id: string; update: Partial<LessonObject> }
  | { type: "move-object"; id: string; x: number; y: number }
  | { type: "erase-object"; id: string }
  | { type: "highlight"; id: string | null }
  | { type: "focus"; id: string | null }
  | { type: "command"; command: LessonCommand }
  | { type: "undo" | "redo" | "reset"; initial: LessonObject[] };

const snapshot = (state: BoardState): BoardSnapshot => ({ authored: state.authored, student: state.student, highlighted: state.highlighted, focused: state.focused });
const withHistory = (state: BoardState): BoardState => ({ ...state, undo: [...state.undo, snapshot(state)], redo: [] });
export const createBoardState = (authored: LessonObject[]): BoardState => ({ authored: structuredClone(authored), student: [], highlighted: null, focused: null, undo: [], redo: [] });
export function boardReducer(state: BoardState, action: BoardAction): BoardState {
  if (action.type === "snapshot") return withHistory(state);
  if (action.type === "set-objects") return { ...state, authored: action.authored, student: [], highlighted: null, focused: null, undo: [], redo: [] };
  if (action.type === "replay") return { ...state, authored: structuredClone(action.authored), highlighted: null, focused: null };
  if (action.type === "undo") {
    const previous = state.undo.at(-1); return previous ? { ...state, ...previous, undo: state.undo.slice(0, -1), redo: [...state.redo, snapshot(state)] } : state;
  }
  if (action.type === "redo") {
    const next = state.redo.at(-1); return next ? { ...state, ...next, redo: state.redo.slice(0, -1), undo: [...state.undo, snapshot(state)] } : state;
  }
  if (action.type === "reset") return createBoardState(action.initial);
  if (action.type === "highlight") return { ...state, highlighted: action.id };
  if (action.type === "focus") return { ...state, focused: action.id };
  if (action.type === "command") {
    const command = action.command;
    if (command.type === "highlight") return { ...state, highlighted: command.id };
    if (command.type === "focus") return { ...state, focused: command.id };
    if (command.type === "erase") return { ...state, authored: state.authored.filter(item => item.id !== command.id), highlighted: state.highlighted === command.id ? null : state.highlighted };
    if (command.type === "move") return { ...state, authored: state.authored.map(item => item.id === command.id ? { ...item, x: command.x, y: command.y } : item) };
    if (command.type === "draw" || command.type === "annotate") return { ...state, authored: [...state.authored.filter(item => item.id !== command.object.id), structuredClone(command.object)] };
    return state;
  }
  if (action.type === "add-student") return { ...withHistory(state), student: [...state.student, action.object] };
  if (action.type === "update-student") return { ...state, student: state.student.map(item => item.id === action.id ? { ...item, ...action.update } : item) };
  if (action.type === "move-object") return { ...state, authored: state.authored.map(item => item.id === action.id ? { ...item, x: action.x, y: action.y } : item), student: state.student.map(item => item.id === action.id ? { ...item, x: action.x, y: action.y } : item) };
  if (action.type === "erase-object") return { ...withHistory(state), authored: state.authored.filter(item => item.id !== action.id), student: state.student.filter(item => item.id !== action.id), highlighted: state.highlighted === action.id ? null : state.highlighted };
  return state;
}

// Future RAG lesson generator contract: produce a validated, transportable plan.
// Future avatar/board contract only: gesture cues can name a board target; no live
// avatar transport, timing service, or synchronization implementation is implied.
export type TeacherGestureIntent = { gesture: "point" | "open-palm" | "emphasize"; targetObjectId?: string; durationMs?: number };
export type LessonPlanEnvelope = { version: 1; plan: LessonPlan; gestureIntents?: TeacherGestureIntent[] };
export function validateLessonEnvelope(value: unknown): LessonPlanEnvelope {
  if (!value || typeof value !== "object" || (value as Partial<LessonPlanEnvelope>).version !== 1) throw new Error("Unsupported lesson envelope version.");
  const envelope = value as LessonPlanEnvelope;
  const plan = validateLessonPlan(envelope.plan);
  if (envelope.gestureIntents !== undefined && (!Array.isArray(envelope.gestureIntents) || envelope.gestureIntents.some(intent => !intent || !["point", "open-palm", "emphasize"].includes(intent.gesture) || (intent.durationMs !== undefined && (!Number.isFinite(intent.durationMs) || intent.durationMs <= 0)) || (intent.targetObjectId !== undefined && !plan.objects.some(item => item.id === intent.targetObjectId))))) throw new Error("Gesture intent is invalid or references an unknown target.");
  return { ...envelope, plan };
}
