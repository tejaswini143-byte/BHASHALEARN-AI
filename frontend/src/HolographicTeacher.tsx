import { Suspense, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { Link } from "react-router-dom";
import type { AvatarSyncFrame } from "./avatarSync";
import "./holographic-teacher.css";

type Pose = "idle" | "speaking" | "listening" | "thinking" | "paused" | "pointing";
type Lesson = "geometry" | "fractions" | "solar";
type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "paused" | "interrupted" | "error";
const states: Pose[] = ["idle", "speaking", "listening", "thinking", "paused", "pointing"];
const lessonCopy: Record<Lesson, { title: string; formula: string; note: string }> = {
  geometry: { title: "Right triangles", formula: "a² + b² = c²", note: "The squares on the legs equal the square on the hypotenuse." },
  fractions: { title: "Equivalent fractions", formula: "1/2 = 2/4", note: "Multiply the numerator and denominator by the same number." },
  solar: { title: "Planetary orbits", formula: "F = Gm₁m₂/r²", note: "Gravity keeps planets in curved paths around the Sun." },
};

export type HolographicVoiceState = VoiceState;
export type HolographicVoiceSource = {
  getState: () => VoiceState;
  getFrame: () => AvatarSyncFrame;
  subscribe: (listener: () => void) => () => void;
  subscribeFrames: (listener: () => void) => () => void;
};
const silentFrame: AvatarSyncFrame = { generation: 0, state: "idle", mode: "silent", language: "mixed", currentTimeMs: 0, viseme: "sil" };
const silentVoiceSource: HolographicVoiceSource = {
  getState: () => "idle", getFrame: () => silentFrame, subscribe: () => () => undefined, subscribeFrames: () => () => undefined,
};
function supportsWebGL() {
  try { const canvas = document.createElement("canvas"); return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl")); }
  catch { return false; }
}

function useVoiceSnapshot(source: HolographicVoiceSource) {
  const state = useSyncExternalStore(source.subscribe, source.getState, source.getState);
  const [frame, setFrame] = useState<AvatarSyncFrame>(source.getFrame());
  useEffect(() => source.subscribeFrames(() => setFrame(source.getFrame())), [source]);
  return { state: state as VoiceState, frame };
}

function SparkField({ reduced, low }: { reduced: boolean; low: boolean }) {
  const points = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const data = new Float32Array((low ? 100 : 280) * 3);
    for (let i = 0; i < data.length; i += 3) {
      data[i] = (Math.random() - 0.5) * 10;
      data[i + 1] = Math.random() * 5.2;
      data[i + 2] = (Math.random() - 0.5) * 5;
    }
    return data;
  }, [low]);
  useFrame((_, delta) => { if (points.current && !reduced) points.current.rotation.y += delta * 0.018; });
  return <points ref={points} position={[0, 0.2, -1]}><bufferGeometry><bufferAttribute attach="attributes-position" args={[positions, 3]} /></bufferGeometry><pointsMaterial color="#72eaff" size={0.035} transparent opacity={0.72} sizeAttenuation depthWrite={false} /></points>;
}

function HoloTeacher({ pose, frame, reduced }: { pose: Pose; frame: AvatarSyncFrame; reduced: boolean }) {
  const body = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const gaze = useRef<THREE.Group>(null);
  const blink = useRef<(THREE.Mesh | null)[]>([]);
  const material = useMemo(() => new THREE.MeshPhysicalMaterial({ color: "#8eeaff", emissive: "#087cbb", emissiveIntensity: 0.7, metalness: 0.32, roughness: 0.24, transparent: true, opacity: 0.78, transmission: 0.08, clearcoat: 0.8, side: THREE.DoubleSide }), []);
  const accent = useMemo(() => new THREE.MeshBasicMaterial({ color: "#a5f5ff", transparent: true, opacity: 0.88 }), []);
  useEffect(() => () => { material.dispose(); accent.dispose(); }, [material, accent]);
  useFrame(({ clock }, delta) => {
    if (reduced) return;
    const t = clock.elapsedTime;
    if (body.current) body.current.position.y = Math.sin(t * 1.15) * 0.035;
    if (head.current) {
      head.current.rotation.y = THREE.MathUtils.damp(head.current.rotation.y, Math.sin(t * 0.42) * 0.09, 3, delta);
      head.current.rotation.z = THREE.MathUtils.damp(head.current.rotation.z, pose === "thinking" ? -0.12 : pose === "listening" ? 0.07 : 0, 4, delta);
    }
    const speak = pose === "speaking" || frame.state === "playing";
    const open = speak && frame.viseme !== "sil" ? ({ aa: 0.095, oh: 0.073, ee: 0.044, mm: 0.018, fv: 0.026, th: 0.045 } as Record<string, number>)[frame.viseme] ?? 0.04 : 0.012;
    if (mouth.current) mouth.current.scale.y = THREE.MathUtils.damp(mouth.current.scale.y, open, 16, delta);
    if (leftArm.current) leftArm.current.rotation.z = THREE.MathUtils.damp(leftArm.current.rotation.z, pose === "speaking" ? 0.52 + Math.sin(t * 2.1) * 0.12 : pose === "listening" ? 0.12 : pose === "pointing" ? 0.16 : 0.02 + Math.sin(t * 0.9) * 0.03, 3.5, delta);
    if (rightArm.current) rightArm.current.rotation.z = THREE.MathUtils.damp(rightArm.current.rotation.z, pose === "pointing" ? -0.9 : pose === "speaking" ? -0.48 - Math.sin(t * 2.4) * 0.13 : pose === "thinking" ? -0.12 : 0, 3.5, delta);
    if (gaze.current) { gaze.current.position.x = Math.sin(t * 0.8) * 0.035; gaze.current.position.y = Math.sin(t * 0.6) * 0.012; }
    const phase = t % 4.1;
    const blinkY = phase > 3.92 && phase < 4.08 ? 0.018 : 0.055;
    blink.current.forEach(eye => { if (eye) eye.scale.y = THREE.MathUtils.damp(eye.scale.y, blinkY, 26, delta); });
  });
  return <group ref={body} position={[-1.05, 0, 0]}>
    {/* Labeled hologram proxy: no licensed or photorealistic rigged character exists in this baseline. */}
    <mesh position={[0, 1.22, 0]} material={material}><capsuleGeometry args={[0.39, 0.96, 8, 24]} /></mesh>
    <mesh position={[0, 1.55, 0.03]} material={accent}><torusGeometry args={[0.3, 0.012, 8, 48]} /></mesh>
    <mesh position={[-0.17, 0.39, 0]} material={material}><capsuleGeometry args={[0.13, 0.56, 6, 14]} /></mesh>
    <mesh position={[0.17, 0.39, 0]} material={material}><capsuleGeometry args={[0.13, 0.56, 6, 14]} /></mesh>
    <mesh position={[0, 1.82, 0]} material={material}><cylinderGeometry args={[0.12, 0.14, 0.22, 16]} /></mesh>
    <group ref={head} position={[0, 2.13, 0]}>
      <mesh material={material}><sphereGeometry args={[0.37, 32, 28]} /></mesh>
      <mesh position={[0, 0.16, -0.025]} material={material}><sphereGeometry args={[0.4, 28, 20, 0, Math.PI * 2, 0, 1.8]} /></mesh>
      <mesh position={[0, -0.085, 0.344]} material={accent} ref={mouth}><sphereGeometry args={[0.062, 16, 10]} /></mesh>
      <group ref={gaze}>
        {[-0.13, 0.13].map((x, index) => <group key={x} position={[x, 0.02, 0.324]}><mesh material={accent} ref={node => { blink.current[index] = node; }} position={[0, 0.015, 0]}><sphereGeometry args={[0.052, 12, 8]} /></mesh><mesh position={[0, 0, 0.028]}><sphereGeometry args={[0.02, 12, 10]} /><meshBasicMaterial color="#12253f" /></mesh></group>)}
      </group>
      <mesh position={[0, 0.11, -0.06]} material={material}><sphereGeometry args={[0.24, 24, 16, 0, Math.PI * 2, 0, 1.5]} /></mesh>
    </group>
    <group ref={leftArm} position={[-0.43, 1.58, 0]}><mesh position={[-0.22, -0.34, 0]} rotation={[0, 0, 0.16]} material={material}><capsuleGeometry args={[0.13, 0.54, 6, 14]} /></mesh><mesh position={[-0.4, -0.67, 0.02]} material={accent}><sphereGeometry args={[0.11, 16, 12]} /></mesh></group>
    <group ref={rightArm} position={[0.43, 1.58, 0]}><mesh position={[0.22, -0.34, 0]} rotation={[0, 0, -0.16]} material={material}><capsuleGeometry args={[0.13, 0.54, 6, 14]} /></mesh><mesh position={[0.4, -0.67, 0.02]} material={accent}><sphereGeometry args={[0.11, 16, 12]} /></mesh></group>
    <mesh position={[0, 2.84, 0]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.75, 0.012, 8, 64]} /><meshBasicMaterial color="#bf8bff" transparent opacity={0.7} /></mesh>
    <mesh position={[0, 1.42, 0]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.56, 0.009, 6, 64]} /><meshBasicMaterial color="#52dfff" transparent opacity={0.46} /></mesh>
  </group>;
}

function TeachingObjects({ lesson }: { lesson: Lesson }) {
  const info = lessonCopy[lesson];
  return <group position={[1.5, 1.35, -0.15]}>
    <mesh position={[0, 0.16, -0.08]}><boxGeometry args={[2.3, 1.35, 0.045]} /><meshPhysicalMaterial color="#7dc8f1" emissive="#1673aa" emissiveIntensity={0.26} transparent opacity={0.18} roughness={0.16} metalness={0.25} transmission={0.15} /></mesh>
    <mesh position={[0, 0.16, -0.045]}><boxGeometry args={[2.3, 1.35, 0.035]} /><meshBasicMaterial color="#70dfff" wireframe transparent opacity={0.2} /></mesh>
    {lesson === "geometry" ? <group position={[0, -0.1, 0.08]}><mesh><coneGeometry args={[0.52, 0.75, 3]} /><meshBasicMaterial color="#89ebff" wireframe transparent opacity={0.9} /></mesh><mesh rotation={[0, 0, Math.PI / 2]}><torusGeometry args={[0.33, 0.009, 6, 36, Math.PI / 2]} /><meshBasicMaterial color="#c091ff" /></mesh></group> : lesson === "fractions" ? <group position={[0, -0.08, 0.08]}><mesh><circleGeometry args={[0.35, 48]} /><meshBasicMaterial color="#85eaff" transparent opacity={0.16} side={THREE.DoubleSide} /></mesh><mesh><torusGeometry args={[0.35, 0.014, 6, 48]} /><meshBasicMaterial color="#85eaff" /></mesh><mesh rotation={[0, 0, Math.PI / 2]}><boxGeometry args={[0.7, 0.012, 0.01]} /><meshBasicMaterial color="#be8cff" /></mesh></group> : <group position={[0, -0.08, 0.08]}>{[0.17, 0.3, 0.43].map((radius, i) => <mesh key={radius} rotation={[Math.PI / 2, 0, i * 0.45]}><torusGeometry args={[radius, 0.009, 6, 40]} /><meshBasicMaterial color={i === 1 ? "#c394ff" : "#85eaff"} /></mesh>)}<mesh><sphereGeometry args={[0.11, 16, 12]} /><meshBasicMaterial color="#fff0a8" /></mesh></group>}
    <Html position={[0, 0.82, 0.1]} center transform distanceFactor={5}><article className="ht-label"><strong>{info.title}</strong><span>{info.formula}</span><small>{info.note}</small></article></Html>
  </group>;
}

function ClassroomScene({ pose, frame, lesson, reduced, low }: { pose: Pose; frame: AvatarSyncFrame; lesson: Lesson; reduced: boolean; low: boolean }) {
  return <>
    <color attach="background" args={["#030a1c"]} /><fog attach="fog" args={["#030a1c", 10, 24]} />
    <ambientLight intensity={0.55} color="#cae8ff" /><directionalLight position={[-3, 7, 5]} intensity={1.6} color="#d9f2ff" />
    <pointLight position={[-2, 2.8, 1]} intensity={18} distance={7} color="#24d8ff" /><pointLight position={[3, 2.6, -1]} intensity={12} distance={8} color="#9361ff" />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.08, 0]}><circleGeometry args={[10, 64]} /><meshStandardMaterial color="#0b1731" metalness={0.3} roughness={0.42} /></mesh>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.055, 0]}><ringGeometry args={[3.1, 3.13, 80]} /><meshBasicMaterial color="#28dafa" transparent opacity={0.58} /></mesh>
    <mesh position={[0, 2.5, -2.4]}><boxGeometry args={[10.3, 5.3, 0.1]} /><meshPhysicalMaterial color="#3576a5" transparent opacity={0.07} roughness={0.1} metalness={0.35} transmission={0.72} side={THREE.DoubleSide} /></mesh>
    <mesh position={[0, 2.5, -2.33]}><boxGeometry args={[10.35, 5.35, 0.035]} /><meshBasicMaterial color="#68cfff" wireframe transparent opacity={0.12} /></mesh>
    <mesh position={[-2.8, 2.3, 0.6]} rotation={[0, 0, -0.24]}><planeGeometry args={[0.03, 4.8]} /><meshBasicMaterial color="#8c71ff" transparent opacity={0.11} /></mesh>
    {!low && Array.from({ length: 5 }, (_, i) => <mesh key={i} position={[-2.4 + i * 0.25, 2.2, 0.7]} rotation={[0, 0, -0.24]}><planeGeometry args={[0.006, 4.2]} /><meshBasicMaterial color="#71eaff" transparent opacity={0.07} /></mesh>)}
    <SparkField reduced={reduced} low={low} /><HoloTeacher pose={pose} frame={frame} reduced={reduced} /><TeachingObjects lesson={lesson} />
    <OrbitControls makeDefault target={[0, 1.55, 0]} enablePan={false} minDistance={5} maxDistance={10} minPolarAngle={0.8} maxPolarAngle={1.45} enableDamping={!reduced} />
  </>;
}

export function HolographicTeacher({ voiceSource = silentVoiceSource }: { voiceSource?: HolographicVoiceSource }) {
  const { state: voiceState, frame } = useVoiceSnapshot(voiceSource);
  const [pose, setPose] = useState<Pose>("idle");
  const [lesson, setLesson] = useState<Lesson>("geometry");
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [low, setLow] = useState(false);
  const [webgl] = useState(supportsWebGL);
  useEffect(() => { const media = window.matchMedia("(prefers-reduced-motion: reduce)"), change = () => setReduced(media.matches); media.addEventListener("change", change); return () => media.removeEventListener("change", change); }, []);
  const activePose: Pose = voiceState === "speaking" ? "speaking" : voiceState === "listening" ? "listening" : voiceState === "thinking" ? "thinking" : voiceState === "paused" || voiceState === "interrupted" ? "paused" : pose;
  return <main className="ht-page">
    <header className="ht-header"><Link to="/" className="ht-brand"><span>✦</span> BHASHA<span>LEARN</span><small> AI</small></Link><Link to="/immersive">Immersive classroom ↗</Link></header>
    <section className="ht-intro"><div><span className="ht-kicker">INT-19 · HOLOGRAPHIC TEACHER</span><h1>Learn in <em>three dimensions.</em></h1><p>Explore concepts beside an animated holographic teaching companion.</p></div><div className="ht-model-note" role="status"><strong>ANIMATED PROTOTYPE</strong><span>No licensed rigged avatar is present in the verified baseline.</span></div></section>
    <section className="ht-layout" aria-label="Holographic teaching experience">
      <div className="ht-stage" aria-label="Interactive holographic classroom">
        {webgl ? <Canvas dpr={low ? [1, 1] : [1, 1.35]} camera={{ position: [0.1, 2.8, 7.2], fov: 42 }} gl={{ antialias: !low, alpha: false, powerPreference: "low-power" }} frameloop={reduced ? "demand" : "always"} fallback={<p>3D rendering is unavailable. Use the lesson controls and concept summary.</p>}><Suspense fallback={null}><ClassroomScene pose={activePose} frame={frame} lesson={lesson} reduced={reduced} low={low} /></Suspense></Canvas> : <div className="ht-fallback" role="alert"><span aria-hidden="true">✧</span><strong>3D view unavailable</strong><p>Continue with the lesson explanation and controls below.</p></div>}
        <div className="ht-stage-tag">✦ HOLOGRAM CLASSROOM <span>LOCAL PROTOTYPE</span></div>
        <div className="ht-caption" aria-live="polite">{voiceState === "error" ? "Voice connection error" : voiceState === "interrupted" ? "Speech interrupted" : `${activePose} · ${frame.mode === "silent" ? "voice sync idle" : frame.mode}`}</div>
      </div>
      <aside className="ht-controls" aria-label="Teacher and lesson controls">
        <label>Teacher state<select value={pose} onChange={event => setPose(event.target.value as Pose)}>{states.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
        <label>Spatial lesson<select value={lesson} onChange={event => setLesson(event.target.value as Lesson)}><option value="geometry">Geometry · right triangles</option><option value="fractions">Math · fractions</option><option value="solar">Science · planetary orbits</option></select></label>
        <section className="ht-concept"><span>FLOATING CONCEPT</span><h2>{lessonCopy[lesson].title}</h2><strong>{lessonCopy[lesson].formula}</strong><p>{lessonCopy[lesson].note}</p><button type="button" onClick={() => setPose("pointing")}>Point to explanation</button></section>
        <label className="ht-check"><input type="checkbox" checked={reduced} onChange={event => setReduced(event.target.checked)} /> Reduce motion</label>
        <label className="ht-check"><input type="checkbox" checked={low} onChange={event => setLow(event.target.checked)} /> Low-performance graphics</label>
        <p className="ht-note">Animation accepts the INT10C voice bridge through its typed adapter. No live provider is called here.</p>
      </aside>
    </section>
    <footer className="ht-footer">Translucent stylized geometry is a labeled fallback, not a photorealistic avatar. Character fidelity awaits a rights-cleared rigged model.</footer>
  </main>;
}
