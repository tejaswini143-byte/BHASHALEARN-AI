export type BilingualText = { en: string; te: string };
export type VisualLessonId = "solar-system" | "geometry" | "pendulum";
export type VisualLesson = {
  id: VisualLessonId;
  subject: BilingualText;
  topic: BilingualText;
  title: BilingualText;
  description: BilingualText;
  objectives: BilingualText[];
  takeaways: BilingualText[];
  steps: { title: BilingualText; explanation: BilingualText }[];
};

export const visualLessons: VisualLesson[] = [
  {
    id: "solar-system", subject: { en: "Space science", te: "అంతరిక్ష విజ్ఞానం" }, topic: { en: "Planetary orbits", te: "గ్రహ కక్ష్యలు" },
    title: { en: "A tour of the solar system", te: "సౌర కుటుంబ యాత్ర" },
    description: { en: "Explore how the planets travel around the Sun.", te: "గ్రహాలు సూర్యుని చుట్టూ ఎలా తిరుగుతాయో అన్వేషించండి." },
    objectives: [{ en: "Identify the eight planets in order.", te: "ఎనిమిది గ్రహాలను క్రమంగా గుర్తించండి." }, { en: "Compare orbital periods.", te: "కక్ష్య కాలాలను పోల్చండి." }],
    takeaways: [{ en: "Planets farther from the Sun take longer to complete an orbit.", te: "సూర్యునికి దూరంగా ఉన్న గ్రహాలు ఒక కక్ష్యను పూర్తి చేయడానికి ఎక్కువ సమయం తీసుకుంటాయి." }],
    steps: [
      { title: { en: "Meet the Sun", te: "సూర్యుడిని తెలుసుకోండి" }, explanation: { en: "The Sun's gravity keeps the planets in orbit.", te: "సూర్యుని గురుత్వాకర్షణ గ్రహాలను కక్ష్యలో ఉంచుతుంది." } },
      { title: { en: "Choose a planet", te: "ఒక గ్రహాన్ని ఎంచుకోండి" }, explanation: { en: "Select any planet to compare its orbit and year.", te: "దాని కక్ష్య మరియు సంవత్సరాన్ని పోల్చడానికి ఏదైనా గ్రహాన్ని ఎంచుకోండి." } },
      { title: { en: "Change time", te: "సమయాన్ని మార్చండి" }, explanation: { en: "Increase the time scale to see orbital motion more quickly.", te: "కక్ష్య చలనాన్ని వేగంగా చూడటానికి సమయ స్థాయిని పెంచండి." } },
    ],
  },
  {
    id: "geometry", subject: { en: "Mathematics", te: "గణితం" }, topic: { en: "3D solid shapes", te: "త్రిమితీయ ఘన ఆకారాలు" },
    title: { en: "Inspect 3D shapes", te: "త్రిమితీయ ఆకారాలను పరిశీలించండి" },
    description: { en: "Rotate a cube, sphere, and cylinder to compare their features.", te: "ఘనం, గోళం మరియు స్థూపాన్ని తిప్పి వాటి లక్షణాలను పోల్చండి." },
    objectives: [{ en: "Compare faces, edges, and vertices.", te: "ముఖాలు, అంచులు మరియు శీర్షాలను పోల్చండి." }, { en: "Connect dimensions to area and volume.", te: "కొలతలను వైశాల్యం మరియు ఘనపరిమాణంతో అనుసంధానించండి." }],
    takeaways: [{ en: "A sphere has a curved surface and no flat faces, straight edges, or vertices.", te: "గోళానికి వక్ర ఉపరితలం ఉంటుంది; సమతల ముఖాలు, సరళ అంచులు లేదా శీర్షాలు ఉండవు." }],
    steps: [
      { title: { en: "Choose a solid", te: "ఘన ఆకారాన్ని ఎంచుకోండి" }, explanation: { en: "Use the shape selector to inspect a cube, sphere, or cylinder.", te: "ఘనం, గోళం లేదా స్థూపాన్ని పరిశీలించడానికి ఆకార ఎంపికను ఉపయోగించండి." } },
      { title: { en: "Rotate and resize", te: "తిప్పి పరిమాణం మార్చండి" }, explanation: { en: "Change the view angle and side length or radius.", te: "వీక్షణ కోణం మరియు భుజం లేదా వ్యాసార్థాన్ని మార్చండి." } },
      { title: { en: "Read the measurements", te: "కొలతలను చదవండి" }, explanation: { en: "Compare the visible features with each solid's formula.", te: "కనిపించే లక్షణాలను ప్రతి ఘన ఆకారపు సూత్రంతో పోల్చండి." } },
    ],
  },
  {
    id: "pendulum", subject: { en: "Physics", te: "భౌతిక శాస్త్రం" }, topic: { en: "Periodic motion", te: "ఆవర్తన చలనం" },
    title: { en: "Pendulum motion", te: "లోలకం చలనం" },
    description: { en: "Explore how length and gravity affect a pendulum's period.", te: "లోలకం ఆవర్తన కాలంపై పొడవు మరియు గురుత్వాకర్షణ ప్రభావాన్ని అన్వేషించండి." },
    objectives: [{ en: "Relate length and gravity to period.", te: "పొడవు మరియు గురుత్వాకర్షణను ఆవర్తన కాలంతో అనుసంధానించండి." }, { en: "Distinguish a model from a real pendulum.", te: "నమూనాను నిజమైన లోలకం నుండి వేరు చేయండి." }],
    takeaways: [{ en: "For small swings, a longer pendulum has a longer period.", te: "చిన్న ఊగిసలాటలలో, పొడవైన లోలకానికి ఎక్కువ ఆవర్తన కాలం ఉంటుంది." }],
    steps: [
      { title: { en: "Set the length", te: "పొడవును సెట్ చేయండి" }, explanation: { en: "Adjust the distance from the pivot to the bob.", te: "ఆధారం నుండి బరువు వరకు దూరాన్ని మార్చండి." } },
      { title: { en: "Change gravity", te: "గురుత్వాకర్షణను మార్చండి" }, explanation: { en: "Compare the motion under different gravitational accelerations.", te: "వివిధ గురుత్వ త్వరణాల వద్ద చలనాన్ని పోల్చండి." } },
      { title: { en: "Compare periods", te: "ఆవర్తన కాలాలను పోల్చండి" }, explanation: { en: "The small-angle model estimates period from length and gravity.", te: "చిన్న కోణ నమూనా పొడవు మరియు గురుత్వం నుండి ఆవర్తన కాలాన్ని అంచనా వేస్తుంది." } },
    ],
  },
];

export type SolarPlanet = { id: string; name: BilingualText; orbit: number; orbitalDays: number; color: string; description: BilingualText };
export const solarPlanets: SolarPlanet[] = [
  { id: "mercury", name: { en: "Mercury", te: "బుధుడు" }, orbit: 1.25, orbitalDays: 88, color: "#b8a99a", description: { en: "The smallest planet and the closest to the Sun.", te: "అతి చిన్న గ్రహం మరియు సూర్యునికి అత్యంత దగ్గరలో ఉంటుంది." } },
  { id: "venus", name: { en: "Venus", te: "శుక్రుడు" }, orbit: 1.72, orbitalDays: 225, color: "#e9ba79", description: { en: "A rocky planet with a very thick atmosphere.", te: "చాలా దట్టమైన వాతావరణం కలిగిన రాతి గ్రహం." } },
  { id: "earth", name: { en: "Earth", te: "భూమి" }, orbit: 2.25, orbitalDays: 365, color: "#48aaff", description: { en: "Our home planet; one orbit takes about one year.", te: "మన నివాస గ్రహం; ఒక కక్ష్యకు సుమారు ఒక సంవత్సరం పడుతుంది." } },
  { id: "mars", name: { en: "Mars", te: "కుజుడు" }, orbit: 2.8, orbitalDays: 687, color: "#f07858", description: { en: "A cold, rocky planet often called the red planet.", te: "ఎర్ర గ్రహం అని పిలిచే చల్లని రాతి గ్రహం." } },
  { id: "jupiter", name: { en: "Jupiter", te: "గురుడు" }, orbit: 3.55, orbitalDays: 4333, color: "#d9a77d", description: { en: "The largest planet, with many moons.", te: "అనేక ఉపగ్రహాలు కలిగిన అతి పెద్ద గ్రహం." } },
  { id: "saturn", name: { en: "Saturn", te: "శని" }, orbit: 4.3, orbitalDays: 10759, color: "#e5d08e", description: { en: "A gas giant known for its bright rings.", te: "ప్రకాశవంతమైన వలయాలకు ప్రసిద్ధి చెందిన వాయు మహాగ్రహం." } },
  { id: "uranus", name: { en: "Uranus", te: "యురేనస్" }, orbit: 5.05, orbitalDays: 30687, color: "#83d6df", description: { en: "An ice giant that rotates on a strongly tilted axis.", te: "వాలిన అక్షంపై తిరిగే మంచు మహాగ్రహం." } },
  { id: "neptune", name: { en: "Neptune", te: "నెప్ట్యూన్" }, orbit: 5.8, orbitalDays: 60190, color: "#5479ec", description: { en: "A distant ice giant with powerful winds.", te: "బలమైన గాలులు కలిగిన దూరపు మంచు మహాగ్రహం." } },
];

export function planetPosition(planet: SolarPlanet, elapsedSeconds: number, timeScale: number): [number, number] {
  if (!Number.isFinite(elapsedSeconds) || !Number.isFinite(timeScale)) return [planet.orbit, 0];
  const days = Math.max(0, elapsedSeconds) * Math.max(0, timeScale);
  const angle = (days / planet.orbitalDays) * Math.PI * 2;
  return [planet.orbit * Math.cos(angle), planet.orbit * Math.sin(angle)];
}

export type ShapeKind = "cube" | "sphere" | "cylinder";
export function shapeMeasurements(kind: ShapeKind, size: number) {
  if (!Number.isFinite(size) || size <= 0) throw new RangeError("Size must be a positive finite number.");
  if (kind === "cube") return { faces: 6, edges: 12, vertices: 8, formula: "V = a³", volume: size ** 3, surfaceArea: 6 * size ** 2 };
  if (kind === "sphere") return { faces: 0, edges: 0, vertices: 0, formula: "V = 4πr³/3", volume: 4 * Math.PI * size ** 3 / 3, surfaceArea: 4 * Math.PI * size ** 2 };
  if (kind === "cylinder") return { faces: 3, edges: 2, vertices: 0, formula: "V = πr²h", volume: Math.PI * size ** 2 * (2 * size), surfaceArea: 2 * Math.PI * size * (size + 2 * size) };
  throw new RangeError("Unsupported shape.");
}

export function pendulumPeriod(lengthMeters: number, gravity: number): number {
  if (!Number.isFinite(lengthMeters) || lengthMeters <= 0) throw new RangeError("Length must be a positive finite number.");
  if (!Number.isFinite(gravity) || gravity <= 0) throw new RangeError("Gravity must be a positive finite number.");
  return 2 * Math.PI * Math.sqrt(lengthMeters / gravity);
}

export type VisualControls = { lessonId: VisualLessonId; selectedPlanet: string; timeScale: number; shape: ShapeKind; size: number; rotation: number; length: number; gravity: number; playing: boolean; step: number };
export const initialVisualControls: VisualControls = { lessonId: "solar-system", selectedPlanet: "earth", timeScale: 30, shape: "cube", size: 1.2, rotation: 25, length: 1, gravity: 9.81, playing: false, step: -1 };
export type VisualControlAction = { type: "lesson"; id: VisualLessonId } | { type: "planet"; id: string } | { type: "time-scale"; value: number } | { type: "shape"; value: ShapeKind } | { type: "size"; value: number } | { type: "rotation"; value: number } | { type: "length"; value: number } | { type: "gravity"; value: number } | { type: "play" } | { type: "pause" } | { type: "step"; delta: number; stepCount: number } | { type: "reset" };
export function visualControlsReducer(state: VisualControls, action: VisualControlAction): VisualControls {
  switch (action.type) {
    case "lesson": return visualLessons.some(lesson => lesson.id === action.id) ? { ...initialVisualControls, lessonId: action.id } : state;
    case "planet": return solarPlanets.some(planet => planet.id === action.id) ? { ...state, selectedPlanet: action.id } : state;
    case "time-scale": return Number.isFinite(action.value) ? { ...state, timeScale: Math.max(0, Math.min(100, action.value)) } : state;
    case "shape": return ["cube", "sphere", "cylinder"].includes(action.value) ? { ...state, shape: action.value } : state;
    case "size": return Number.isFinite(action.value) ? { ...state, size: Math.max(0.25, Math.min(3, action.value)) } : state;
    case "rotation": return Number.isFinite(action.value) ? { ...state, rotation: Math.max(-180, Math.min(180, action.value)) } : state;
    case "length": return Number.isFinite(action.value) ? { ...state, length: Math.max(0.5, Math.min(3, action.value)) } : state;
    case "gravity": return Number.isFinite(action.value) ? { ...state, gravity: Math.max(0.1, Math.min(25, action.value)) } : state;
    case "play": return { ...state, playing: true };
    case "pause": return { ...state, playing: false };
    case "step": return Number.isFinite(action.delta) && Number.isFinite(action.stepCount) && action.stepCount > 0 ? { ...state, playing: false, step: Math.max(-1, Math.min(action.stepCount - 1, state.step + Math.trunc(action.delta))) } : state;
    case "reset": return { ...initialVisualControls, lessonId: state.lessonId };
  }
}

// Future narration adapters can consume this stable, provider-agnostic event.
export type VisualNarrationRequest = { lessonId: VisualLessonId; stepIndex: number; language: "en" | "te"; text: string };
