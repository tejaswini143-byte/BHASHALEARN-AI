import { Component, Suspense, useCallback, useEffect, useMemo, useReducer, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import { initialVisualControls, pendulumPeriod, planetPosition, shapeMeasurements, solarPlanets, visualControlsReducer, visualLessons, type ShapeKind, type SolarPlanet, type VisualLessonId } from "./visualLessonsModel";
import { fetchVisualLessonCatalog, generateVisualLesson, visualLessonApiError } from "./visualLessonsApi";
import { createVisualLessonEnvelope, validateGeneratedVisualLessonEnvelope, validateVisualLessonEnvelope, type GeneratedVisualLessonEnvelope } from "./visualLessonContract";
import type { VisualLesson } from "./visualLessonsModel";
import { VisualFlowBoard } from "./VisualFlowBoard";
import { HouseLessonScene } from "./HouseLessonScene";
import "./visual-lessons.css";

class SimulationBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* Keep the lesson controls available when a graphics device fails. */ }
  render() { return this.state.failed ? <SimulationFallback/> : this.props.children; }
}

function SimulationFallback() {
  return <section className="vl-fallback" role="alert"><span aria-hidden="true">◇</span><div><h3>3D simulation unavailable</h3><p>This device or browser cannot start the 3D view. Use the lesson text and controls below, or try a browser with WebGL enabled.</p></div></section>;
}

function OrbitingPlanet({ planet, timeScale, selected, language, onSelect }: { planet: SolarPlanet; timeScale: number; selected: boolean; language: "en" | "te"; onSelect: () => void }) {
  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!group.current) return;
    const [x, z] = planetPosition(planet, clock.elapsedTime, timeScale);
    group.current.position.set(x, 0, z);
  });
  return <group ref={group} onClick={onSelect}>
    <mesh><sphereGeometry args={[selected ? 0.18 : 0.13, 24, 18]}/><meshStandardMaterial color={planet.color} emissive={planet.color} emissiveIntensity={selected ? 0.35 : 0.08}/></mesh>
    {selected && <mesh><sphereGeometry args={[0.25, 24, 18]}/><meshBasicMaterial color="#74e9ff" wireframe transparent opacity={0.42}/></mesh>}
    {selected && <Html position={[0, 0.35, 0]} center distanceFactor={8} style={{ pointerEvents: "none" }}><span className="vl-planet-label">{planet.name[language]}</span></Html>}
  </group>;
}

function SolarSystemScene({ selected, timeScale, language, onSelect, reduced }: { selected: string; timeScale: number; language: "en" | "te"; onSelect: (id: string) => void; reduced: boolean }) {
  return <>
    <color attach="background" args={["#081126"]}/><ambientLight intensity={0.55}/><pointLight position={[0, 1, 0]} intensity={28} distance={12} color="#ffc76d"/>
    <mesh><sphereGeometry args={[0.43, 32, 24]}/><meshStandardMaterial color="#ffbf5e" emissive="#ff8f32" emissiveIntensity={2.1}/></mesh>
    {solarPlanets.map(planet => <group key={planet.id} rotation={[0, 0, 0]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[planet.orbit - 0.004, planet.orbit + 0.004, 96]}/><meshBasicMaterial color={selected === planet.id ? "#9b83ff" : "#43628e"} transparent opacity={0.55}/></mesh>
      <OrbitingPlanet planet={planet} timeScale={reduced ? 0 : timeScale} selected={selected === planet.id} language={language} onSelect={() => onSelect(planet.id)}/>
    </group>)}
  </>;
}

function GeometryScene({ shape, size, rotation, reduced }: { shape: ShapeKind; size: number; rotation: number; reduced: boolean }) {
  const root = useRef<THREE.Group>(null);
  useFrame((_state, delta) => { if (!reduced && root.current) root.current.rotation.y += delta * 0.18; });
  const geometry = useMemo(() => shape === "cube" ? new THREE.BoxGeometry(size, size, size) : shape === "sphere" ? new THREE.SphereGeometry(size, 32, 24) : new THREE.CylinderGeometry(size, size, size * 2, 40), [shape, size]);
  const edges = useMemo(() => new THREE.EdgesGeometry(geometry), [geometry]);
  useEffect(() => () => { geometry.dispose(); edges.dispose(); }, [edges, geometry]);
  return <>
    <color attach="background" args={["#081126"]}/><ambientLight intensity={0.7}/><directionalLight position={[3, 4, 5]} intensity={3} color="#c8e9ff"/><pointLight position={[-3, 1, 2]} intensity={16} color="#8b6aff"/>
    <group ref={root} rotation={[0.32, rotation * Math.PI / 180, 0]}>
      <mesh geometry={geometry}><meshStandardMaterial color="#46cfe9" metalness={0.38} roughness={0.25} transparent opacity={0.86} side={THREE.DoubleSide}/></mesh>
      {shape !== "sphere" && <lineSegments geometry={edges}><lineBasicMaterial color="#e1fbff"/></lineSegments>}
    </group>
  </>;
}

function PendulumScene({ length, gravity, playing, reduced, resetKey }: { length: number; gravity: number; playing: boolean; reduced: boolean; resetKey: number }) {
  const pivot = useRef<THREE.Group>(null);
  const elapsed = useRef(0);
  useEffect(() => { elapsed.current = 0; if (pivot.current) pivot.current.rotation.z = 0; }, [resetKey]);
  const period = pendulumPeriod(length, gravity);
  useFrame((_state, delta) => {
    if (!pivot.current || !playing || reduced) return;
    elapsed.current += delta;
    pivot.current.rotation.z = 0.38 * Math.cos((2 * Math.PI * elapsed.current) / period);
  });
  return <>
    <color attach="background" args={["#081126"]}/><ambientLight intensity={0.72}/><directionalLight position={[2, 3, 4]} intensity={2.5} color="#c8e9ff"/><pointLight position={[-2, 1, 2]} intensity={11} color="#8b6aff"/>
    <group ref={pivot} position={[0, 1.45, 0]}>
      <mesh><sphereGeometry args={[0.09, 20, 16]}/><meshStandardMaterial color="#a48aff" emissive="#805dff" emissiveIntensity={0.5}/></mesh>
      <mesh position={[0, -length / 2, 0]}><cylinderGeometry args={[0.018, 0.018, length, 10]}/><meshStandardMaterial color="#78dff6" metalness={0.4}/></mesh>
      <mesh position={[0, -length, 0]}><sphereGeometry args={[0.19, 24, 20]}/><meshStandardMaterial color="#58d5ed" metalness={0.5} roughness={0.22}/></mesh>
    </group>
  </>;
}

function AuthGate({ children }: { children: (student: Student) => ReactNode }) {
  const navigate = useNavigate();
  const [student, setStudent] = useState<Student | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) { navigate("/login", { replace: true, state: { from: "/visual-lessons" } }); return; }
    getCurrentStudent(token).then(value => { if (active) setStudent(value); }).catch(cause => {
      if (!active) return;
      if (cause instanceof ApiError && cause.status === 401) { clearToken(); navigate("/login", { replace: true, state: { from: "/visual-lessons" } }); }
      else setError(cause instanceof Error ? cause.message : "Could not verify your student account.");
    }).finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [navigate]);
  if (checking) return <main className="vl-auth-state" role="status">Preparing your visual lessons…</main>;
  if (!student) return <main className="vl-auth-state"><h1>Visual lessons unavailable</h1><p role="alert">{error}</p><Link to="/dashboard">Return to dashboard</Link></main>;
  return children(student);
}

function LessonWorkspace({ student }: { student: Student }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedSession = searchParams.get("session");
  const [controls, dispatch] = useReducer(visualControlsReducer, initialVisualControls);
  const [catalog, setCatalog] = useState<VisualLesson[]>(visualLessons);
  const [catalogStatus, setCatalogStatus] = useState("Loading authenticated lesson catalog…");
  const [sessionId, setSessionId] = useState("");
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionStatus, setSessionStatus] = useState("Connecting to your learning session…");
  const [generatedEnvelopes, setGeneratedEnvelopes] = useState<Partial<Record<VisualLessonId, GeneratedVisualLessonEnvelope>>>({});
  const [quizResponses, setQuizResponses] = useState<string[]>([]);
  const [quizDraft, setQuizDraft] = useState("");
  const [quizRevealed, setQuizRevealed] = useState(false);
  const [generationTopic, setGenerationTopic] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generationMessage, setGenerationMessage] = useState("");
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const controller = new AbortController();
    fetchVisualLessonCatalog(token, controller.signal)
      .then(items => { if (!controller.signal.aborted) { setCatalog(items); dispatch({ type: "reset" }); setReplayKey(key => key + 1); setCatalogStatus("Lessons synchronized with backend"); } })
      .catch(error => { if (!controller.signal.aborted) setCatalogStatus(visualLessonApiError(error)); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    (async () => {
      try {
        const sessions = await request<{ id: string; topic: string }[]>("/sessions?limit=100", { headers });
        let selected = requestedSession ? sessions.find(item => item.id === requestedSession) : sessions[0];
        if (requestedSession && !selected) setSessionStatus("The requested learning session was unavailable; using your latest session.");
        if (!selected && !requestedSession) {
          selected = await request<{ id: string; topic: string }>("/sessions", { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ topic: "Interactive visual lessons", language: "english" }) });
        }
        if (!active || !selected) return;
        setSessionId(selected.id);
        if (requestedSession !== selected.id) setSearchParams({ session: selected.id }, { replace: true });
      } catch (cause) {
        if (active) setSessionStatus(cause instanceof Error ? cause.message : "Could not open your learning session.");
      }
    })();
    return () => { active = false; };
  }, [requestedSession, setSearchParams]);
  useEffect(() => {
    if (!sessionId) return;
    let active = true;
    const token = getToken();
    if (!token) return;
    setSessionReady(false);
    request<{ state: null | { envelope: unknown; current_step: number; paused: boolean; completed: boolean; interactions: Record<string, string | number | boolean>; quiz_responses: string[] } }>(`/visual-lessons/session-state?session_id=${encodeURIComponent(sessionId)}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(({ state }) => {
        if (!active || !state) return;
        const envelope = state.envelope as { version?: number };
        const valid = envelope?.version === 2 ? validateGeneratedVisualLessonEnvelope(state.envelope) : validateVisualLessonEnvelope(state.envelope);
        setCatalog(items => [...items.filter(item => item.id !== valid.lesson.id), valid.lesson]);
        if (envelope.version === 2) setGeneratedEnvelopes(items => ({ ...items, [valid.lesson.id]: valid as GeneratedVisualLessonEnvelope }));
        dispatch({ type: "lesson", id: valid.lesson.id });
        if (state.current_step >= 0) dispatch({ type: "step", delta: state.current_step + 1, stepCount: valid.lesson.steps.length });
        setQuizResponses(state.quiz_responses ?? []);
        setQuizDraft(state.quiz_responses?.[0] ?? "");
        setQuizRevealed(Boolean(state.quiz_responses?.length));
        const interaction = state.interactions;
        if (typeof interaction.selected_planet === "string") dispatch({ type: "planet", id: interaction.selected_planet });
        if (typeof interaction.time_scale === "number") dispatch({ type: "time-scale", value: interaction.time_scale });
        if (typeof interaction.shape === "string" && ["cube", "sphere", "cylinder"].includes(interaction.shape)) dispatch({ type: "shape", value: interaction.shape as ShapeKind });
        for (const key of ["size", "rotation", "length", "gravity"] as const) if (typeof interaction[key] === "number") dispatch({ type: key, value: interaction[key] });
        setCatalogStatus(state.completed ? "Lesson restored · completed progress saved" : "Lesson restored · progress saved");
      })
      .catch(cause => { if (active) setSessionStatus(cause instanceof Error ? cause.message : "Saved lesson progress could not be restored."); })
      .finally(() => { if (active) setSessionReady(true); });
    return () => { active = false; };
  }, [sessionId]);
  const [language, setLanguage] = useState<"en" | "te">("en");
  const immersiveUrl = `/immersive?lesson=${encodeURIComponent(controls.lessonId)}`;
  const [reduced, setReduced] = useState(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [replayKey, setReplayKey] = useState(0);
  const [smartboardOpen, setSmartboardOpen] = useState(true);
  const lesson = catalog.find(item => item.id === controls.lessonId);
  useEffect(() => {
    if (!sessionId || !sessionReady || !lesson) return;
    const token = getToken();
    if (!token) return;
    const envelope = generatedEnvelopes[lesson.id] ?? createVisualLessonEnvelope(lesson);
    const timer = window.setTimeout(() => {
      request<{ state: unknown }>("/visual-lessons/session-state", {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          envelope,
          current_step: controls.step,
          paused: !controls.playing,
          completed: controls.step >= lesson.steps.length - 1 && (!lesson.questions?.length || quizResponses.length > 0),
          interactions: { selected_planet: controls.selectedPlanet, time_scale: controls.timeScale, shape: controls.shape, size: controls.size, rotation: controls.rotation, length: controls.length, gravity: controls.gravity },
          quiz_responses: quizResponses,
        }),
      }).then(() => setSessionStatus("Progress saved to your learning session")).catch(cause => setSessionStatus(cause instanceof Error ? cause.message : "Progress could not be saved."));
    }, 450);
    return () => window.clearTimeout(timer);
  }, [sessionId, sessionReady, lesson, controls, generatedEnvelopes, quizResponses]);
  const voiceUrl = `/voice?topic=${encodeURIComponent(lesson?.title[language] ?? "Visual lesson")}`;
  const step = lesson && controls.step >= 0 ? lesson.steps[controls.step] : null;
  const selectedPlanet = solarPlanets.find(planet => planet.id === controls.selectedPlanet) ?? solarPlanets[2];
  const measurements = shapeMeasurements(controls.shape, controls.size);
  const subjectOptions = useMemo(() => [...new Map(catalog.map(item => [item.subject.en, item.subject])).entries()], [catalog]);
  const filteredLessons = catalog.filter(item => item.subject.en === (lesson?.subject.en ?? catalog[0]?.subject.en));
  const advance = useCallback((delta: number) => { if (lesson) dispatch({ type: "step", delta, stepCount: lesson.steps.length }); }, [lesson]);
  const reset = useCallback(() => { dispatch({ type: "reset" }); setReplayKey(key => key + 1); setQuizResponses([]); setQuizDraft(""); setQuizRevealed(false); }, []);
  async function createAiLesson(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const topic = generationTopic.trim();
    if (!topic || !sessionId) return;
    const token = getToken();
    if (!token) { setGenerationMessage("Please sign in again to generate a lesson."); return; }
    setGenerating(true);
    setGenerationMessage("");
    try {
      const result = await generateVisualLesson(token, sessionId, topic, controls.lessonId, language === "te" ? "telugu" : "english");
      setCatalog(current => [...current.filter(item => item.id !== result.lesson.id), result.lesson]);
      setGeneratedEnvelopes(current => ({ ...current, [result.lesson.id]: result }));
      setQuizResponses([]);
      setQuizDraft("");
      setQuizRevealed(false);
      dispatch({ type: "lesson", id: result.lesson.id });
      if (result.scene.kind === "solar-system") dispatch({ type: "time-scale", value: Number(result.scene.parameters.time_scale) });
      if (result.scene.kind === "geometry") {
        dispatch({ type: "shape", value: result.scene.parameters.shape as ShapeKind });
        dispatch({ type: "size", value: Number(result.scene.parameters.size) });
      }
      if (result.scene.kind === "pendulum") {
        dispatch({ type: "length", value: Number(result.scene.parameters.length) });
        dispatch({ type: "gravity", value: Number(result.scene.parameters.gravity) });
      }
      setGenerationMessage(language === "en" ? "Validated AI lesson loaded. Its scene uses the supported simulation controls." : "ధృవీకరించిన AI పాఠం సిద్ధమైంది. ఇది మద్దతు ఉన్న అనుకరణ నియంత్రణలను ఉపయోగిస్తుంది.");
    } catch (cause) {
      setGenerationMessage(cause instanceof Error ? cause.message : "Could not generate a lesson.");
    } finally { setGenerating(false); }
  }
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)"), update = () => setReduced(media.matches);
    media.addEventListener("change", update); return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.target instanceof HTMLElement && ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(event.target.tagName)) return;
      if (event.key === "ArrowRight") { event.preventDefault(); advance(1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); advance(-1); }
      if (event.key.toLowerCase() === "r") reset();
    };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [advance, reset]);

  if (!lesson) return <main className="vl-empty"><h1>No visual lessons available</h1><p>There are no lessons in this catalog yet.</p></main>;
  return <main className="vl-page" aria-label="Interactive visual lessons">
    <header className="vl-header"><Link to="/dashboard" className="vl-brand" aria-label="BHASHALEARN AI dashboard"><span>✦</span> BHASHA<span>LEARN</span><small> AI</small></Link><div className="vl-student"><i aria-hidden="true"/>{student.display_name || "Student"}</div><Link to="/dashboard" className="vl-exit">Exit lessons ↗</Link></header>
    <div className="vl-shell">
      <section className="vl-title"><div><span className="vl-eyebrow">VISUAL LESSON STUDIO</span><h1>{language === "en" ? <>Learn by <span>seeing.</span></> : <>చూస్తూ <span>నేర్చుకోండి.</span></>}</h1><p>{language === "en" ? "Learn everyday English and Telugu with an interactive picture lesson." : "ఇంటరాక్టివ్ చిత్ర పాఠంతో రోజువారీ ఇంగ్లీష్ మరియు తెలుగు నేర్చుకోండి."}</p></div><label className="vl-language">Explanation language<select aria-label="Explanation language" value={language} onChange={event => setLanguage(event.target.value as "en" | "te")}><option value="en">English</option><option value="te">తెలుగు</option></select></label></section>
      <HouseLesson language={language}/>
      <details className="vl-more-lessons"><summary>{language === "en" ? "Explore interactive science and AI-generated lessons" : "ఇంటరాక్టివ్ సైన్స్ మరియు AI పాఠాలను చూడండి"}</summary>
      <p role="status" aria-live="polite" className="vl-meta">{catalogStatus}</p>
      <p role="status" aria-live="polite" className="vl-meta">{sessionStatus}</p>
      <form className="vl-ai-generate" onSubmit={event => void createAiLesson(event)}>
        <label htmlFor="vl-ai-topic">{language === "en" ? "Create a bilingual lesson with Gemini" : "Geminiతో ద్విభాషా పాఠం రూపొందించండి"}</label>
        <div><input id="vl-ai-topic" value={generationTopic} onChange={event => setGenerationTopic(event.target.value)} minLength={2} maxLength={200} placeholder={language === "en" ? "Enter a topic for this lesson" : "పాఠం కోసం అంశాన్ని నమోదు చేయండి"}/><button type="submit" disabled={generating || !sessionId || !generationTopic.trim()}>{generating ? (language === "en" ? "Generating…" : "రూపొందిస్తోంది…") : (language === "en" ? "Generate lesson" : "పాఠం రూపొందించు")}</button></div>
        {generationMessage && <p role={generationMessage.startsWith("Could not") || generationMessage.startsWith("Please sign") ? "alert" : "status"}>{generationMessage}</p>}
      </form>
      <section className="vl-picker" aria-label="Lesson selection"><label>Subject<select aria-label="Choose subject" value={lesson.subject.en} onChange={event => { const next = catalog.find(item => item.subject.en === event.target.value); if (next) { dispatch({ type: "lesson", id: next.id }); setReplayKey(key => key + 1); setQuizResponses([]); setQuizDraft(""); setQuizRevealed(false); } }}>{subjectOptions.map(([key, text]) => <option key={key} value={key}>{text[language]}</option>)}</select></label><label>Topic<select aria-label="Choose topic" value={lesson.id} onChange={event => { dispatch({ type: "lesson", id: event.target.value as VisualLessonId }); setReplayKey(key => key + 1); setQuizResponses([]); setQuizDraft(""); setQuizRevealed(false); }}>{filteredLessons.map(item => <option key={item.id} value={item.id}>{item.topic[language]}</option>)}</select></label><span className="vl-meta">{lesson.subject[language]} · {lesson.topic[language]}</span></section>
      <section className="vl-lesson-head"><div><h2>{lesson.title[language]}</h2><p>{lesson.description[language]}</p></div><div className="vl-lesson-actions"><button type="button" className="vl-board-toggle" aria-expanded={smartboardOpen} onClick={() => setSmartboardOpen(value => !value)}>{smartboardOpen ? (language === "en" ? "Hide smartboard" : "స్మార్ట్‌బోర్డ్ దాచు") : (language === "en" ? "Open smartboard" : "స్మార్ట్‌బోర్డ్ తెరువు")}</button><button className="vl-reset" onClick={reset}>↺ Reset lesson</button></div></section>
      {smartboardOpen && <VisualFlowBoard lesson={lesson} activeStep={Math.max(0, controls.step)} language={language} sessionId={sessionId} onStepChange={index => dispatch({ type: "step", delta: index - controls.step, stepCount: lesson.steps.length })} onReset={reset}/>}
      <section className="vl-layout">
        <div className="vl-primary">
          <div className="vl-simulation" aria-label={`${lesson.title.en} 3D simulation`}>
            <SimulationBoundary><Canvas camera={{ position: [0, 4.2, 8.5], fov: 45 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: false, powerPreference: "low-power" }} frameloop={reduced ? "demand" : "always"} fallback={<SimulationFallback/>} aria-label={`${lesson.title.en} interactive 3D scene`}>
              <Suspense fallback={null}>{controls.lessonId === "solar-system" ? <SolarSystemScene selected={controls.selectedPlanet} timeScale={controls.timeScale} language={language} onSelect={id => dispatch({ type: "planet", id })} reduced={reduced}/> : controls.lessonId === "geometry" ? <GeometryScene shape={controls.shape} size={controls.size} rotation={controls.rotation} reduced={reduced}/> : <PendulumScene length={controls.length} gravity={controls.gravity} playing={controls.playing} reduced={reduced} resetKey={replayKey}/>}</Suspense>
              <OrbitControls makeDefault enableDamping minDistance={3} maxDistance={16} />
            </Canvas></SimulationBoundary>
            <div className="vl-scene-caption" aria-live="polite">{controls.lessonId === "solar-system" ? `${language === "en" ? "Selected planet" : "ఎంచుకున్న గ్రహం"}: ${selectedPlanet.name[language]}` : controls.lessonId === "geometry" ? (language === "en" ? `${controls.shape} · ${measurements.faces} faces · ${measurements.edges} edges · ${measurements.vertices} vertices` : `${controls.shape} · ${measurements.faces} ముఖాలు · ${measurements.edges} అంచులు · ${measurements.vertices} శీర్షాలు`) : (language === "en" ? `${controls.playing ? "Motion running" : "Paused"} · period ${pendulumPeriod(controls.length, controls.gravity).toFixed(2)} s` : `${controls.playing ? "చలనం కొనసాగుతోంది" : "నిలిపివేయబడింది"} · ఆవర్తన కాలం ${pendulumPeriod(controls.length, controls.gravity).toFixed(2)} s`)}</div>
          </div>
          <div className="vl-controls" aria-label="Simulation controls">
            {controls.lessonId === "solar-system" && <><div className="vl-planet-picker" role="group" aria-label="Choose planet">{solarPlanets.map(planet => <button key={planet.id} className={selectedPlanet.id === planet.id ? "selected" : ""} aria-pressed={selectedPlanet.id === planet.id} onClick={() => dispatch({ type: "planet", id: planet.id })}>{planet.name[language]}</button>)}</div><label className="vl-range">{language === "en" ? "Time scale" : "సమయ స్థాయి"}<input aria-label="Time scale" type="range" min="0" max="100" value={controls.timeScale} onChange={event => dispatch({ type: "time-scale", value: Number(event.target.value) })}/><output>{controls.timeScale}×</output></label><p className="vl-disclaimer">{language === "en" ? "Educational model: planet sizes, orbit spacing, and distances are not proportional to real scale." : "విద్యా నమూనా: గ్రహ పరిమాణాలు, కక్ష్య అంతరాలు మరియు దూరాలు నిజమైన నిష్పత్తిలో లేవు."}</p></>}
            {controls.lessonId === "geometry" && <><label>Shape<select aria-label="Choose shape" value={controls.shape} onChange={event => dispatch({ type: "shape", value: event.target.value as ShapeKind })}><option value="cube">{language === "en" ? "Cube" : "ఘనం"}</option><option value="sphere">{language === "en" ? "Sphere" : "గోళం"}</option><option value="cylinder">{language === "en" ? "Cylinder" : "స్థూపం"}</option></select></label><label className="vl-range">{language === "en" ? "Rotate" : "తిప్పండి"}<input aria-label="Rotate shape" type="range" min="-180" max="180" value={controls.rotation} onChange={event => dispatch({ type: "rotation", value: Number(event.target.value) })}/><output>{controls.rotation}°</output></label><label className="vl-range">{language === "en" ? "Size" : "పరిమాణం"}<input aria-label="Shape size" type="range" min="0.25" max="3" step="0.05" value={controls.size} onChange={event => dispatch({ type: "size", value: Number(event.target.value) })}/><output>{controls.size.toFixed(2)}</output></label></>}
            {controls.lessonId === "pendulum" && <><label className="vl-range">{language === "en" ? "Length" : "పొడవు"}<input aria-label="Pendulum length" type="range" min="0.5" max="3" step="0.05" value={controls.length} onChange={event => dispatch({ type: "length", value: Number(event.target.value) })}/><output>{controls.length.toFixed(2)} m</output></label><label className="vl-range">{language === "en" ? "Gravity" : "గురుత్వం"}<input aria-label="Gravity" type="range" min="0.1" max="25" step="0.1" value={controls.gravity} onChange={event => dispatch({ type: "gravity", value: Number(event.target.value) })}/><output>{controls.gravity.toFixed(1)} m/s²</output></label><div className="vl-playback"><button onClick={() => dispatch({ type: controls.playing ? "pause" : "play" })}>{controls.playing ? (language === "en" ? "Pause" : "నిలిపివేయి") : (language === "en" ? "Resume" : "కొనసాగించు")}</button><button onClick={reset}>{language === "en" ? "Reset" : "మళ్లీ ప్రారంభించు"}</button><strong>T ≈ {pendulumPeriod(controls.length, controls.gravity).toFixed(2)} s</strong></div><p className="vl-disclaimer">{language === "en" ? "Simplified model: small swing angle, point mass, massless string, and no air resistance. Period uses T = 2π√(L/g)." : "సరళ నమూనా: చిన్న ఊగిసలాట కోణం, బిందు ద్రవ్యరాశి, ద్రవ్యరహిత తాడు మరియు గాలి నిరోధం లేదు. T = 2π√(L/g)."}</p></>}
          </div>
          {controls.lessonId === "geometry" && <section className="vl-facts" aria-label="Shape description"><h3>{language === "en" ? "Shape facts" : "ఆకార వివరాలు"}</h3><p>{language === "en" ? `${controls.shape} has ${measurements.faces} faces, ${measurements.edges} edges, and ${measurements.vertices} vertices. ${controls.shape === "sphere" ? "Its surface is curved, with no flat faces, straight edges, or vertices." : "Rotate the model to inspect its surfaces and boundaries."}` : `${controls.shape}కు ${measurements.faces} ముఖాలు, ${measurements.edges} అంచులు మరియు ${measurements.vertices} శీర్షాలు ఉన్నాయి. ${controls.shape === "sphere" ? "దాని ఉపరితలం వక్రంగా ఉంటుంది; సమతల ముఖాలు, సరళ అంచులు లేదా శీర్షాలు ఉండవు." : "ఉపరితలాలు మరియు సరిహద్దులను పరిశీలించడానికి నమూనాను తిప్పండి."}`}</p><div><span>{measurements.formula}</span><span>{language === "en" ? "Volume" : "ఘనపరిమాణం"}: {measurements.volume.toFixed(2)}</span><span>{language === "en" ? "Surface area" : "ఉపరితల వైశాల్యం"}: {measurements.surfaceArea.toFixed(2)}</span></div></section>}
        </div>
        <aside className="vl-side">
          <section className="vl-card"><span className="vl-eyebrow">{language === "en" ? "LEARNING OBJECTIVES" : "అభ్యసన లక్ష్యాలు"}</span><h3>{language === "en" ? "By the end, you can…" : "పూర్తయ్యే సరికి మీరు…"}</h3><ul>{lesson.objectives.map((item, index) => <li key={index}>{item[language]}</li>)}</ul></section>
          <section className="vl-card vl-guided"><span className="vl-eyebrow">{language === "en" ? "GUIDED EXPLORATION" : "మార్గదర్శక అన్వేషణ"}</span><h3>{step ? step.title[language] : (language === "en" ? "Start exploring" : "అన్వేషణ ప్రారంభించండి")}</h3><p aria-live="polite">{step ? step.explanation[language] : lesson.description[language]}</p><div className="vl-step-actions"><button aria-label="Previous lesson step" onClick={() => advance(-1)} disabled={controls.step < 0}>←</button><span>{Math.max(0, controls.step + 1)} / {lesson.steps.length}</span><button aria-label="Next lesson step" onClick={() => advance(1)} disabled={controls.step >= lesson.steps.length - 1}>→</button></div><button className="vl-replay" onClick={reset}>↺ {language === "en" ? "Reset and replay" : "మళ్లీ ప్రారంభించండి"}</button><small>← → {language === "en" ? "steps · R reset" : "దశలు · R మళ్లీ ప్రారంభించు"}</small></section>
          <section className="vl-card vl-crossmode" aria-label="Continue learning"><span className="vl-eyebrow">{language === "en" ? "CONTINUE LEARNING" : "అభ్యాసాన్ని కొనసాగించండి"}</span><h3>{language === "en" ? "Learn with your AI teacher" : "AI ఉపాధ్యాయునితో నేర్చుకోండి"}</h3><p>{language === "en" ? "Continue this topic in the immersive smartboard classroom or discuss it with the voice tutor." : "ఈ అంశాన్ని స్మార్ట్‌బోర్డ్ తరగతిలో కొనసాగించండి లేదా వాయిస్ ట్యూటర్‌తో చర్చించండి."}</p><div className="vl-crossmode-links"><Link to={immersiveUrl}>3D classroom</Link><Link to={voiceUrl}>Voice tutor</Link></div></section>
          <section className="vl-card"><span className="vl-eyebrow">{language === "en" ? "KEY TAKEAWAY" : "ముఖ్యాంశం"}</span><ul>{lesson.takeaways.map((item, index) => <li key={index}>{item[language]}</li>)}</ul></section>
          {controls.lessonId === "solar-system" && <section className="vl-card vl-planet-detail"><span className="vl-eyebrow">{language === "en" ? "PLANET PROFILE" : "గ్రహ పరిచయం"}</span><h3>{selectedPlanet.name[language]}</h3><p>{selectedPlanet.description[language]}</p><strong>{language === "en" ? "Orbital period" : "కక్ష్య కాలం"}: {selectedPlanet.orbitalDays.toLocaleString()} {language === "en" ? "days" : "రోజులు"}</strong></section>}
          {lesson.questions?.[0] && <section className="vl-card vl-quiz" aria-label={language === "en" ? "Lesson question" : "పాఠ ప్రశ్న"}><span className="vl-eyebrow">{language === "en" ? "YOUR TURN" : "మీ వంతు"}</span><h3>{lesson.questions[0].prompt[language]}</h3><form onSubmit={event => { event.preventDefault(); if (!quizDraft.trim()) return; setQuizResponses([quizDraft.trim()]); setQuizRevealed(true); }}><input aria-label={language === "en" ? "Your answer" : "మీ సమాధానం"} value={quizDraft} onChange={event => setQuizDraft(event.target.value)} maxLength={500} disabled={quizRevealed}/><button type="submit" disabled={!quizDraft.trim() || quizRevealed}>{language === "en" ? "Check answer" : "సమాధానం తనిఖీ చేయి"}</button></form>{quizRevealed && <p role="status">{quizDraft.trim().toLocaleLowerCase() === lesson.questions[0].answer[language].trim().toLocaleLowerCase() ? (language === "en" ? "Correct. " : "సరైనది. ") : `${language === "en" ? "Review: " : "మళ్లీ చూడండి: "}${lesson.questions[0].answer[language]}. `}{lesson.questions[0].explanation[language]}</p>}</section>}
          {lesson.activities?.length ? <section className="vl-card"><span className="vl-eyebrow">{language === "en" ? "INTERACTIVE ACTIVITIES" : "ఇంటరాక్టివ్ కార్యకలాపాలు"}</span><ul>{lesson.activities.map((activity, index) => <li key={index}>{activity.instruction[language]}</li>)}</ul></section> : null}
          {lesson.completion_criteria?.length ? <section className="vl-card"><span className="vl-eyebrow">{language === "en" ? "COMPLETION CRITERIA" : "పూర్తి ప్రమాణాలు"}</span><ul>{lesson.completion_criteria.map((criterion, index) => <li key={index}>{criterion[language]}</li>)}</ul><p role="status">{controls.step >= lesson.steps.length - 1 && (!lesson.questions?.length || quizResponses.length > 0) ? (language === "en" ? "Lesson completed · progress saved" : "పాఠం పూర్తయింది · పురోగతి భద్రపరచబడింది") : (language === "en" ? "Continue the steps and answer the question to complete this lesson." : "పాఠాన్ని పూర్తి చేయడానికి దశలను కొనసాగించి ప్రశ్నకు సమాధానం ఇవ్వండి.")}</p></section> : null}
        </aside>
      </section>
      <p className="vl-motion"><label><input type="checkbox" checked={reduced} onChange={event => setReduced(event.target.checked)}/>{language === "en" ? "Reduce motion" : "చలనాన్ని తగ్గించు"}</label><span>{language === "en" ? "Keyboard: ← → lesson steps · R reset" : "కీబోర్డ్: ← → పాఠ దశలు · R మళ్లీ ప్రారంభించు"}</span></p>
      </details>
    </div>
  </main>;
}

function HouseLesson({ language }: { language: "en" | "te" }) {
  const [step, setStep] = useState(0);
  const [answer, setAnswer] = useState("");
  const [checked, setChecked] = useState(false);
  const copy = language === "en"
    ? { eyebrow: "VISUAL LESSON · ENGLISH + TELUGU", title: "Learn words around the house", description: "Explore the picture, repeat each word, then try a short practice question.", steps: ["Learn words", "Repeat", "Practice", "A quick quiz"], previous: "Previous", next: "Next", quiz: "Which room do we sleep in?", choices: ["Bedroom", "Kitchen", "Garden"], check: "Check answer", correct: "Correct! We sleep in a bedroom.", tryAgain: "Try again. A bedroom is where we sleep.", demo: "Practice lesson · Your choices stay in this lesson and are not sent to your account." }
    : { eyebrow: "చిత్ర పాఠం · ఇంగ్లీష్ + తెలుగు", title: "ఇంటి చుట్టూ పదాలు నేర్చుకోండి", description: "చిత్రాన్ని చూడండి, ప్రతి పదాన్ని పలకండి, తర్వాత చిన్న ప్రశ్నకు సమాధానం ఇవ్వండి.", steps: ["పదాలు నేర్చుకోండి", "పలకండి", "అభ్యసించండి", "చిన్న క్విజ్"], previous: "మునుపటి", next: "తదుపరి", quiz: "మనం ఏ గదిలో నిద్రిస్తాము?", choices: ["పడకగది", "వంటగది", "తోట"], check: "సమాధానం చూడండి", correct: "సరైనది! మనం పడకగదిలో నిద్రిస్తాము.", tryAgain: "మళ్లీ ప్రయత్నించండి. మనం పడకగదిలో నిద్రిస్తాము.", demo: "అభ్యాస పాఠం · మీ ఎంపికలు ఈ పాఠంలోనే ఉంటాయి; ఖాతాకు పంపబడవు." };
  const quiz = step === 3;
  function advance(delta: number) { setStep(current => Math.max(0, Math.min(3, current + delta))); setChecked(false); }
  return <section className="house-lesson" aria-labelledby="house-lesson-title">
    <div className="house-lesson-heading"><div><span className="vl-eyebrow">{copy.eyebrow}</span><h2 id="house-lesson-title">{copy.title}</h2><p>{copy.description}</p></div><span className="house-lesson-badge">{step + 1} / 4</span></div>
    <div className="house-lesson-layout">
      <HouseLessonScene language={language} step={step}/>
      <aside className="house-lesson-steps" aria-label={language === "en" ? "Lesson steps" : "పాఠం దశలు"}>
        <h3>{language === "en" ? "Lesson Steps" : "పాఠం దశలు"}</h3>
        <ol>{copy.steps.map((label, index) => <li key={label} className={index === step ? "active" : index < step ? "complete" : ""}><span aria-hidden="true">{index < step ? "✓" : index + 1}</span>{label}</li>)}</ol>
        {quiz && <form className="house-quiz" onSubmit={event => { event.preventDefault(); setChecked(true); }}><fieldset><legend>{copy.quiz}</legend>{copy.choices.map((choice, index) => <label key={choice}><input type="radio" name="house-room-answer" value={index === 0 ? "bedroom" : choice} checked={answer === (index === 0 ? "bedroom" : choice)} onChange={event => { setAnswer(event.target.value); setChecked(false); }}/>{choice}</label>)}</fieldset><button type="submit" disabled={!answer}>{copy.check}</button>{checked && <p role="status">{answer === "bedroom" ? copy.correct : copy.tryAgain}</p>}</form>}
      </aside>
    </div>
    <div className="house-lesson-footer"><button type="button" onClick={() => advance(-1)} disabled={step === 0}>{copy.previous}</button><button type="button" className="house-next" onClick={() => advance(1)} disabled={step === 3}>{copy.next}</button></div>
    <p className="house-lesson-demo">{copy.demo}</p>
  </section>;
}

export function VisualLessons() { return <AuthGate>{student => <LessonWorkspace student={student}/>}</AuthGate>; }
