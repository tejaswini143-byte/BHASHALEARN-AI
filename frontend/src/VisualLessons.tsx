import { Component, Suspense, useCallback, useEffect, useMemo, useReducer, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, type Student } from "./auth";
import { initialVisualControls, pendulumPeriod, planetPosition, shapeMeasurements, solarPlanets, visualControlsReducer, visualLessons, type ShapeKind, type SolarPlanet, type VisualLessonId } from "./visualLessonsModel";
import { fetchVisualLessonCatalog, visualLessonApiError } from "./visualLessonsApi";
import type { VisualLesson } from "./visualLessonsModel";
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

function OrbitingPlanet({ planet, timeScale, selected, onSelect }: { planet: SolarPlanet; timeScale: number; selected: boolean; onSelect: () => void }) {
  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!group.current) return;
    const [x, z] = planetPosition(planet, clock.elapsedTime, timeScale);
    group.current.position.set(x, 0, z);
  });
  return <group ref={group} onClick={onSelect}>
    <mesh><sphereGeometry args={[selected ? 0.18 : 0.13, 24, 18]}/><meshStandardMaterial color={planet.color} emissive={planet.color} emissiveIntensity={selected ? 0.35 : 0.08}/></mesh>
    {selected && <mesh><sphereGeometry args={[0.25, 24, 18]}/><meshBasicMaterial color="#74e9ff" wireframe transparent opacity={0.42}/></mesh>}
  </group>;
}

function SolarSystemScene({ selected, timeScale, onSelect, reduced }: { selected: string; timeScale: number; onSelect: (id: string) => void; reduced: boolean }) {
  return <>
    <color attach="background" args={["#081126"]}/><ambientLight intensity={0.55}/><pointLight position={[0, 1, 0]} intensity={28} distance={12} color="#ffc76d"/>
    <mesh><sphereGeometry args={[0.43, 32, 24]}/><meshStandardMaterial color="#ffbf5e" emissive="#ff8f32" emissiveIntensity={2.1}/></mesh>
    {solarPlanets.map(planet => <group key={planet.id} rotation={[0, 0, 0]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[planet.orbit - 0.004, planet.orbit + 0.004, 96]}/><meshBasicMaterial color={selected === planet.id ? "#9b83ff" : "#43628e"} transparent opacity={0.55}/></mesh>
      <OrbitingPlanet planet={planet} timeScale={reduced ? 0 : timeScale} selected={selected === planet.id} onSelect={() => onSelect(planet.id)}/>
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
  const [controls, dispatch] = useReducer(visualControlsReducer, initialVisualControls);
  const [catalog, setCatalog] = useState<VisualLesson[]>(visualLessons);
  const [catalogStatus, setCatalogStatus] = useState("Loading authenticated lesson catalog…");
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const controller = new AbortController();
    fetchVisualLessonCatalog(token, controller.signal)
      .then(items => { if (!controller.signal.aborted) { setCatalog(items); dispatch({ type: "reset" }); setReplayKey(key => key + 1); setCatalogStatus("Lessons synchronized with backend"); } })
      .catch(error => { if (!controller.signal.aborted) setCatalogStatus(visualLessonApiError(error)); });
    return () => controller.abort();
  }, []);
  const [language, setLanguage] = useState<"en" | "te">("en");
  const immersiveUrl = `/immersive?lesson=${encodeURIComponent(controls.lessonId)}`;
  const [reduced, setReduced] = useState(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [replayKey, setReplayKey] = useState(0);
  const lesson = catalog.find(item => item.id === controls.lessonId);
  const voiceUrl = `/voice?topic=${encodeURIComponent(lesson?.title[language] ?? "Visual lesson")}`;
  const step = lesson && controls.step >= 0 ? lesson.steps[controls.step] : null;
  const selectedPlanet = solarPlanets.find(planet => planet.id === controls.selectedPlanet) ?? solarPlanets[2];
  const measurements = shapeMeasurements(controls.shape, controls.size);
  const subjectOptions = useMemo(() => [...new Map(catalog.map(item => [item.subject.en, item.subject])).entries()], [catalog]);
  const filteredLessons = catalog.filter(item => item.subject.en === (lesson?.subject.en ?? catalog[0]?.subject.en));
  const advance = useCallback((delta: number) => { if (lesson) dispatch({ type: "step", delta, stepCount: lesson.steps.length }); }, [lesson]);
  const reset = useCallback(() => { dispatch({ type: "reset" }); setReplayKey(key => key + 1); }, []);
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
      <section className="vl-title"><div><span className="vl-eyebrow">INTERACTIVE VISUAL LESSONS</span><h1>Ideas you can <span>explore.</span></h1><p>Choose a subject and topic, then learn by interacting with the model.</p></div><label className="vl-language">Explanation language<select aria-label="Explanation language" value={language} onChange={event => setLanguage(event.target.value as "en" | "te")}><option value="en">English</option><option value="te">తెలుగు</option></select></label></section>
      <p role="status" aria-live="polite" className="vl-meta">{catalogStatus}</p>
      <section className="vl-picker" aria-label="Lesson selection"><label>Subject<select aria-label="Choose subject" value={lesson.subject.en} onChange={event => { const next = catalog.find(item => item.subject.en === event.target.value); if (next) { dispatch({ type: "lesson", id: next.id }); setReplayKey(key => key + 1); } }}>{subjectOptions.map(([key, text]) => <option key={key} value={key}>{text[language]}</option>)}</select></label><label>Topic<select aria-label="Choose topic" value={lesson.id} onChange={event => { dispatch({ type: "lesson", id: event.target.value as VisualLessonId }); setReplayKey(key => key + 1); }}>{filteredLessons.map(item => <option key={item.id} value={item.id}>{item.topic[language]}</option>)}</select></label><span className="vl-meta">{lesson.subject[language]} · {lesson.topic[language]}</span></section>
      <section className="vl-lesson-head"><div><h2>{lesson.title[language]}</h2><p>{lesson.description[language]}</p></div><button className="vl-reset" onClick={reset}>↺ Reset lesson</button></section>
      <section className="vl-layout">
        <div className="vl-primary">
          <div className="vl-simulation" aria-label={`${lesson.title.en} 3D simulation`}>
            <SimulationBoundary><Canvas camera={{ position: [0, 4.2, 8.5], fov: 45 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: false, powerPreference: "low-power" }} frameloop={reduced ? "demand" : "always"} fallback={<SimulationFallback/>} aria-label={`${lesson.title.en} interactive 3D scene`}>
              <Suspense fallback={null}>{controls.lessonId === "solar-system" ? <SolarSystemScene selected={controls.selectedPlanet} timeScale={controls.timeScale} onSelect={id => dispatch({ type: "planet", id })} reduced={reduced}/> : controls.lessonId === "geometry" ? <GeometryScene shape={controls.shape} size={controls.size} rotation={controls.rotation} reduced={reduced}/> : <PendulumScene length={controls.length} gravity={controls.gravity} playing={controls.playing} reduced={reduced} resetKey={replayKey}/>}</Suspense>
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
        </aside>
      </section>
      <p className="vl-motion"><label><input type="checkbox" checked={reduced} onChange={event => setReduced(event.target.checked)}/>{language === "en" ? "Reduce motion" : "చలనాన్ని తగ్గించు"}</label><span>{language === "en" ? "Keyboard: ← → lesson steps · R reset" : "కీబోర్డ్: ← → పాఠ దశలు · R మళ్లీ ప్రారంభించు"}</span></p>
    </div>
  </main>;
}

export function VisualLessons() { return <AuthGate>{student => <LessonWorkspace student={student}/>}</AuthGate>; }
