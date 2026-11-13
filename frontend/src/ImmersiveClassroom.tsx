import { Component, useCallback, useEffect, useState, useSyncExternalStore, type ErrorInfo, type ReactNode } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, type Student } from "./auth";
import { ImmersiveTeacher } from "./TeacherPreview";
import { VoiceTutor } from "./VoiceTutor";
import { immersiveVoiceBridge } from "./immersiveVoiceBridge";
import { playbackReducer, sampleLessons } from "./lessonEngine";
import { cameraPresets, type CameraPreset } from "./immersiveCore";
import "./immersive-classroom.css";

class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* The accessible scene fallback replaces the failed renderer. */ }
  render() { return this.state.failed ? <WebGLFallback/> : this.props.children; }
}

function WebGLFallback() {
  return <section className="ic-fallback" role="alert" aria-label="3D scene unavailable">
    <div className="ic-fallback-orb" aria-hidden="true">✦</div><p className="ic-eyebrow">IMMERSIVE CLASSROOM</p>
    <h1>3D view unavailable</h1><p>Your lesson controls remain available. Continue with the steps in the lesson panel.</p>
  </section>;
}

function ImmersiveRoom({ reduced }: { reduced: boolean }) {
  return <>
    <color attach="background" args={["#050b1b"]}/><fog attach="fog" args={["#050b1b", 13, 30]}/>
    <ambientLight intensity={0.42} color="#c7dafa"/><directionalLight position={[-4, 8, 5]} intensity={2.2} color="#d8eaff" castShadow/>
    <pointLight position={[4, 4, -2]} intensity={28} distance={14} color="#37cfff"/><pointLight position={[-5, 3, -3]} intensity={17} distance={12} color="#835cff"/>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.12, 0]} receiveShadow><circleGeometry args={[14, 96]}/><meshStandardMaterial color="#0b1730" metalness={0.4} roughness={0.48}/></mesh>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.105, 0]}><ringGeometry args={[6.7, 6.76, 96]}/><meshBasicMaterial color="#2878ba" transparent opacity={0.65}/></mesh>
    {[-7, 7].map(x => <group key={x} position={[x, 0, -4]}><mesh position={[0, 2.5, 0]}><cylinderGeometry args={[0.15, 0.22, 5, 20]}/><meshStandardMaterial color="#14213d" metalness={0.48} roughness={0.35} emissive="#4034a2" emissiveIntensity={0.18}/></mesh><pointLight position={[0, 3.3, 0]} intensity={8} distance={6} color="#8b69ff"/></group>)}
    <Stars radius={34} depth={42} count={750} factor={2.2} fade speed={reduced ? 0 : 0.12}/>
  </>;
}

function VoiceFrameScheduler({ reduced }: { reduced: boolean }) {
  const { invalidate } = useThree();
  useEffect(() => reduced ? immersiveVoiceBridge.subscribeFrames(invalidate) : undefined, [invalidate, reduced]);
  return null;
}

function CameraDirector({ preset }: { preset: CameraPreset }) {
  const { camera } = useThree();
  useEffect(() => { const view = cameraPresets[preset]; camera.position.set(...view.position); camera.lookAt(...view.target); }, [camera, preset]);
  return null;
}

function AccessGate({ children }: { children: (student: Student, offlineDemo: boolean) => ReactNode }) {
  const navigate = useNavigate();
  const [student, setStudent] = useState<Student | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  const [offlineDemo, setOfflineDemo] = useState(false);
  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) { navigate("/login", { replace: true, state: { from: "/immersive" } }); return; }
    getCurrentStudent(token).then(value => { if (active) setStudent(value); }).catch(cause => {
      if (!active) return;
      if (cause instanceof ApiError && cause.status === 401) { clearToken(); navigate("/login", { replace: true, state: { from: "/immersive" } }); }
      else if (cause instanceof ApiError && (cause.status === 0 || cause.status >= 500)) {
        setOfflineDemo(true); setStudent({ id: "local-demo", email: "demo@local.invalid", display_name: "Local demo learner" });
      } else setError(cause instanceof Error ? cause.message : "Could not verify your student account.");
    }).finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [navigate]);
  if (checking) return <main className="ic-auth-state" role="status">Preparing your immersive classroom…</main>;
  if (!student) return <main className="ic-auth-state"><h1>Classroom unavailable</h1><p role="alert">{error}</p><Link to="/dashboard">Return to dashboard</Link></main>;
  return children(student, offlineDemo);
}

function ImmersiveExperience({ student, offlineDemo }: { student: Student; offlineDemo: boolean }) {
  const [lessonIndex, setLessonIndex] = useState(0);
  const [playback, setPlayback] = useState({ step: -1, playing: false });
  const [preset, setPreset] = useState<CameraPreset>("overview");
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const voiceState = useSyncExternalStore(immersiveVoiceBridge.subscribe, immersiveVoiceBridge.getState, immersiveVoiceBridge.getState);
  const lesson = sampleLessons[lessonIndex];
  const cameraCycle: CameraPreset[] = ["overview", "teacher", "lesson"];
  const advance = useCallback((action: "next" | "previous") => setPlayback(current => playbackReducer(current, action, lesson.steps.length)), [lesson.steps.length]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)"), update = () => setReduced(media.matches);
    media.addEventListener("change", update); return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!playback.playing) return;
    const id = window.setInterval(() => setPlayback(current => playbackReducer(current, "tick", lesson.steps.length)), 2400);
    return () => window.clearInterval(id);
  }, [lesson.steps.length, playback.playing]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.target instanceof HTMLElement && ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(event.target.tagName)) return;
      if (event.key === "ArrowRight") { event.preventDefault(); advance("next"); }
      if (event.key === "ArrowLeft") { event.preventDefault(); advance("previous"); }
      if (/^[1-3]$/.test(event.key)) setPreset(cameraCycle[Number(event.key) - 1]);
      if (event.key.toLowerCase() === "f") void fullscreen();
    };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [advance]);

  async function fullscreen() {
    const root = document.querySelector<HTMLElement>(".ic-experience");
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await root?.requestFullscreen?.(); } catch { /* Keep the responsive in-page layout if fullscreen is denied. */ }
  }

  const activeStep = playback.step >= 0 ? lesson.steps[playback.step] : null;
  return <main className="ic-experience" aria-label="Immersive classroom">
    <div className="ic-scene"><SceneBoundary><Canvas aria-label="Decorative immersive 3D classroom" shadows dpr={[1, 1.5]} camera={{ position: cameraPresets.overview.position, fov: 39 }} gl={{ antialias: true, alpha: false, powerPreference: "low-power" }} frameloop={reduced ? "demand" : "always"} fallback={<WebGLFallback/>}>
      <CameraDirector preset={preset}/><VoiceFrameScheduler reduced={reduced}/><ImmersiveRoom reduced={reduced}/><ImmersiveTeacher state={activeStep ? "explain" : "idle"} reduced={reduced} voiceState={voiceState}/>
      <OrbitControls makeDefault target={cameraPresets[preset].target} minDistance={5.5} maxDistance={14} minPolarAngle={0.55} maxPolarAngle={1.45} enablePan={false}/>
    </Canvas></SceneBoundary></div>
    <header className="ic-topbar"><Link to="/dashboard" className="ic-brand" aria-label="BHASHALEARN AI dashboard"><span>✦</span> BHASHA<span className="ic-brand-accent">LEARN</span><small> AI</small></Link><div className="ic-student"><i aria-hidden="true"/>{student.display_name || "Student"}{offlineDemo && <span className="ic-offline-status">LOCAL DEMO - BACKEND UNAVAILABLE</span>}<span>·</span><span>IMMERSIVE CLASS</span></div><Link to="/dashboard" className="ic-exit">Exit classroom <span aria-hidden="true">↗</span></Link></header>
    <div className="ic-scene-label"><i aria-hidden="true"/> LIVE 3D LEARNING SPACE</div>
    <p className="ic-avatar-notice" role="status">3D teacher avatar not loaded. Lesson board and voice controls remain available; a licensed rigged character is required for teacher animation.</p>
    <aside className="ic-board" aria-label="Interactive lesson board" aria-live="polite">
      <span className="ic-board-kicker">LESSON BOARD · {lesson.subject}</span>
      <h2>{activeStep?.title || lesson.title}</h2>
      <p>{activeStep?.explanation || lesson.intro}</p>
    </aside>
    <aside className="ic-hud" aria-label="Lesson controls">
      <div className="ic-hud-top"><div><span className="ic-eyebrow">{lesson.subject}</span><h1>{lesson.title}</h1></div><label className="ic-lesson-select">Lesson<select aria-label="Choose lesson" value={lessonIndex} onChange={event => { setLessonIndex(Number(event.target.value)); setPlayback({ step: -1, playing: false }); }}>{sampleLessons.map((item, index) => <option key={item.id} value={index}>{item.title}</option>)}</select></label></div>
      <p className="ic-explanation" aria-live="polite">{activeStep?.explanation || lesson.intro}</p>
      {activeStep && <div className="ic-step-name" aria-live="polite"><span>{String(playback.step + 1).padStart(2, "0")}</span>{activeStep.title}</div>}
      <div className="ic-voice-controls"><span className={`ic-voice-state is-${voiceState}`} data-testid="immersive-voice-state"><i aria-hidden="true"/>{voiceState === "idle" ? "Voice ready - no audio" : voiceState === "listening" ? "Listening" : voiceState === "thinking" ? "Thinking" : voiceState === "speaking" ? "Speaking" : voiceState === "paused" ? "Paused" : voiceState === "interrupted" ? "Speech interrupted" : "Voice unavailable"}</span><button type="button" aria-expanded={voiceOpen} onClick={() => setVoiceOpen(value => !value)}>{voiceOpen ? "Hide voice tutor" : "Open voice tutor"}</button></div>
      <div className="ic-progress" aria-label={`Lesson step ${Math.max(0, playback.step + 1)} of ${lesson.steps.length}`}><span style={{ width: `${Math.max(0, (playback.step + 1) / lesson.steps.length * 100)}%` }}/></div>
      <div className="ic-controls"><button onClick={() => advance("previous")} aria-label="Previous lesson step" disabled={playback.step < 0}>←</button><button className="ic-play" onClick={() => setPlayback(current => playbackReducer(current, current.playing ? "pause" : "play", lesson.steps.length))} aria-label={playback.playing ? "Pause lesson" : "Play lesson"}>{playback.playing ? "Ⅱ" : "▶"}<span>{playback.playing ? "Pause" : "Play lesson"}</span></button><button onClick={() => advance("next")} aria-label="Next lesson step" disabled={playback.step >= lesson.steps.length - 1}>→</button><span className="ic-control-divider"/><label className="ic-motion"><input type="checkbox" checked={reduced} onChange={event => setReduced(event.target.checked)}/> Reduce motion</label></div>
      <details className="ic-shortcuts"><summary>Keyboard controls</summary><span>← → lesson steps · 1–3 camera · F fullscreen</span></details>
    </aside>
    <nav className="ic-camera-nav" aria-label="Camera presets">{cameraCycle.map((value, index) => <button key={value} className={preset === value ? "active" : ""} aria-pressed={preset === value} onClick={() => setPreset(value)}><span>{String(index + 1).padStart(2, "0")}</span>{cameraPresets[value].label}</button>)}<button className="ic-fullscreen" onClick={() => void fullscreen()} aria-label="Toggle fullscreen">⛶</button></nav>
    {voiceOpen && <VoiceTutor immersive forceDemo={offlineDemo} onClose={() => setVoiceOpen(false)}/>}
    <span className="ic-sr-only" aria-live="polite">{playback.step < 0 ? "Lesson introduction" : `Step ${playback.step + 1}: ${activeStep?.title}`}</span>
  </main>;
}

export function ImmersiveClassroom() {
  return <AccessGate>{(student, offlineDemo) => <ImmersiveExperience student={student} offlineDemo={offlineDemo}/>}</AccessGate>;
}
