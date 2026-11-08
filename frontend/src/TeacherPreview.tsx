import { Component, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type ErrorInfo, type ReactNode } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { AnimationMixer, type AnimationClip, type Group, type Object3D } from "three";
import { Link } from "react-router-dom";
import { mapBoardTarget, settledTeacherState, validateTeacherAction, validateVisemeTimeline, visemeAt, type BoardTarget, type Expression, type TeacherAction, type TeacherState, type VisemeFrame } from "./teacherCore";
import { immersiveVoiceBridge, type ImmersiveVoiceState } from "./immersiveVoiceBridge";
import "./teacher-preview.css";

const states: TeacherState[] = ["idle", "walk", "turn", "explain", "point", "listen", "celebrate"];
const expressions: Expression[] = ["neutral", "happy", "curious", "encouraging", "thinking"];
const demoTimeline: VisemeFrame[] = [{ atMs: 0, durationMs: 240, viseme: "aa" }, { atMs: 240, durationMs: 190, viseme: "ee" }, { atMs: 430, durationMs: 210, viseme: "mm" }, { atMs: 640, durationMs: 250, viseme: "oh" }, { atMs: 890, durationMs: 160, viseme: "fv" }, { atMs: 1050, durationMs: 200, viseme: "aa" }];

type TeacherProps = { state: TeacherState; expression: Expression; target: BoardTarget | null; walkTarget: [number, number]; lookTarget: [number, number, number]; viseme: string; reduced: boolean; model: LoadedModel | null };
type LoadedModel = { scene: Group; clips: AnimationClip[] };
type LoadedTeacherProps = Omit<TeacherProps, "target" | "model"> & { model: LoadedModel };

class SceneErrorBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { this.props.onError(); }
  render() { return this.state.failed ? <div className="teacher-scene-error" role="alert">3D preview could not start in this browser. Try enabling WebGL or using a recent desktop browser.</div> : this.props.children; }
}

function Room() {
  return <>
    <color attach="background" args={["#071329"]} />
    <fog attach="fog" args={["#071329", 12, 25]} />
    <ambientLight intensity={0.62} color="#b8d7ff" />
    <directionalLight position={[-4, 7, 4]} intensity={2.1} color="#d7e9ff" castShadow />
    <pointLight position={[0, 4, -4]} intensity={24} distance={13} color="#25cfff" />
    <pointLight position={[5, 3, 2]} intensity={9} distance={9} color="#a450ff" />
    <mesh position={[0, -0.1, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow><planeGeometry args={[24, 24]} /><meshStandardMaterial color="#101d3a" metalness={0.34} roughness={0.4} /></mesh>
    <mesh position={[0, 2.5, -6.4]}><boxGeometry args={[13, 5.2, 0.3]} /><meshStandardMaterial color="#111a33" metalness={0.44} roughness={0.42} /></mesh>
    <mesh position={[0, 2.75, -6.17]}><boxGeometry args={[8.2, 3.45, 0.1]} /><meshBasicMaterial color="#081a35" /></mesh>
    <mesh position={[0, 2.75, -6.1]}><planeGeometry args={[8.05, 3.3]} /><meshBasicMaterial color="#52d9ff" transparent opacity={0.12} /></mesh>
    <mesh position={[0, 2.75, -6.03]}><planeGeometry args={[8.25, 3.5]} /><meshBasicMaterial color="#46dfff" wireframe transparent opacity={0.33} /></mesh>
    <mesh position={[0, 0.06, -4.55]}><boxGeometry args={[9.5, 0.12, 2.3]} /><meshStandardMaterial color="#202950" metalness={0.55} roughness={0.31} /></mesh>
    <mesh position={[0, 0.13, -4.55]}><boxGeometry args={[9.4, 0.04, 2.2]} /><meshStandardMaterial color="#273357" metalness={0.46} roughness={0.32} emissive="#1f4e82" emissiveIntensity={0.15} /></mesh>
    {[-6.4, 6.4].map(x => <mesh key={x} position={[x, 2, -4.2]}><boxGeometry args={[0.05, 3.7, 0.06]} /><meshBasicMaterial color="#8c62ff" /></mesh>)}
    <Stars radius={35} depth={40} count={450} factor={2.3} fade speed={0.1} />
  </>;
}

function PlaceholderTeacher({ state, expression, target, walkTarget, lookTarget, viseme, reduced }: Omit<TeacherProps, "model">) {
  const root = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const clock = useRef(0);
  const pointing = useMemo(() => target ? mapBoardTarget(target) : [0, 2.4, -6] as [number, number, number], [target]);
  useFrame((_, delta) => {
    const syncedSpeaking = immersiveVoiceBridge.getState() === "speaking";
    const syncedViseme = syncedSpeaking ? immersiveVoiceBridge.getFrame().viseme : viseme;
    const openness = syncedViseme === "sil" ? 0.18 : syncedViseme === "aa" ? 1 : syncedViseme === "oh" ? 0.72 : syncedViseme === "ee" ? 0.48 : syncedViseme === "th" ? 0.55 : 0.32;
    if (mouth.current) mouth.current.scale.y = reduced ? openness : THREE.MathUtils.damp(mouth.current.scale.y, openness, 22, delta);
    if (reduced) return;
    clock.current += delta;
    const t = clock.current;
    if (root.current) {
      root.current.position.y = Math.sin(t * 1.45) * 0.035;
      root.current.position.x = THREE.MathUtils.damp(root.current.position.x, walkTarget[0], state === "walk" ? 1.5 : 2.5, delta);
      root.current.position.z = THREE.MathUtils.damp(root.current.position.z, walkTarget[1], state === "walk" ? 1.5 : 2.5, delta);
      const yaw = state === "turn" ? Math.atan2(lookTarget[0] - root.current.position.x, lookTarget[2] - root.current.position.z) : 0;
      root.current.rotation.y = THREE.MathUtils.damp(root.current.rotation.y, yaw, 3, delta);
    }
    if (leftArm.current) leftArm.current.rotation.x = state === "celebrate" ? -2.5 : state === "listen" ? -0.3 : Math.sin(t * 1.1) * 0.06;
    if (rightArm.current) rightArm.current.rotation.x = state === "point" ? -0.55 : state === "explain" ? -1.05 + Math.sin(t * 3.5) * 0.18 : state === "celebrate" ? -2.5 : state === "listen" ? -0.2 : Math.sin(t * 1.3 + 1) * 0.07;
    if (state === "point" && rightArm.current) {
      const toTarget = new THREE.Vector3(...pointing).sub(root.current?.localToWorld(new THREE.Vector3(0.45, 2.15, 0)) ?? new THREE.Vector3());
      rightArm.current.rotation.z = Math.atan2(toTarget.x, toTarget.y) * 0.42;
    } else if (rightArm.current) rightArm.current.rotation.z = state === "explain" ? Math.sin(t * 2.2) * 0.14 : 0;
    if (head.current) { head.current.rotation.z = expression === "curious" ? -0.1 : 0; head.current.rotation.x = state === "listen" ? 0.1 : 0; }
  });
  const blouse = "#f2d9cb";
  return <group ref={root} position={[-2, 0, -0.5]}>
    {/* Clearly marked geometric prototype: production likeness requires a licensed skinned avatar. */}
    <mesh position={[0, 0.95, 0]} castShadow><capsuleGeometry args={[0.36, 0.7, 6, 12]} /><meshStandardMaterial color="#56408b" roughness={0.62} /></mesh>
    <mesh position={[0, 1.45, 0]} castShadow><capsuleGeometry args={[0.42, 0.38, 5, 12]} /><meshStandardMaterial color={blouse} roughness={0.8} /></mesh>
    <mesh position={[-0.15, 0.31, 0]} castShadow><capsuleGeometry args={[0.13, 0.57, 4, 10]} /><meshStandardMaterial color="#242d4c" roughness={0.74} /></mesh>
    <mesh position={[0.15, 0.31, 0]} castShadow><capsuleGeometry args={[0.13, 0.57, 4, 10]} /><meshStandardMaterial color="#242d4c" roughness={0.74} /></mesh>
    <mesh position={[0, 1.78, 0]}><cylinderGeometry args={[0.12, 0.14, 0.22, 12]} /><meshStandardMaterial color="#b88067" roughness={0.76} /></mesh>
    <group ref={head} position={[0, 2.1, 0]}>
      <mesh castShadow><sphereGeometry args={[0.36, 24, 20]} /><meshStandardMaterial color="#d6a589" roughness={0.62} /></mesh>
      <mesh position={[0, 0.17, -0.035]} castShadow><sphereGeometry args={[0.39, 24, 18]} /><meshStandardMaterial color="#302038" roughness={0.86} /></mesh>
      <mesh position={[0, 0.025, 0.315]}><sphereGeometry args={[0.3, 24, 18, 0, Math.PI * 2, 0.4, 2.1]} /><meshStandardMaterial color="#d6a589" roughness={0.65} /></mesh>
      {[-0.12, 0.12].map(x => <mesh key={x} position={[x, 0.025, 0.308]}><sphereGeometry args={[0.025, 10, 8]} /><meshBasicMaterial color="#171b2c" /></mesh>)}
      <mesh ref={mouth} position={[0, -0.095, 0.32]}><capsuleGeometry args={[0.025, 0.055, 3, 6]} /><meshStandardMaterial color={viseme === "sil" ? "#734e4c" : "#6c3049"} /></mesh>
      <mesh position={[0, 0.13, 0.05]}><sphereGeometry args={[0.19, 16, 12, 0, Math.PI * 2, 0, 1.5]} /><meshStandardMaterial color={expression === "happy" || expression === "encouraging" ? "#392037" : "#302038"} roughness={0.7} /></mesh>
    </group>
    <group ref={leftArm} position={[-0.45, 1.5, 0]}><mesh position={[0, -0.34, 0]} rotation={[0, 0, 0.12]} castShadow><capsuleGeometry args={[0.13, 0.53, 4, 10]} /><meshStandardMaterial color={blouse} roughness={0.78} /></mesh><mesh position={[0, -0.67, 0.01]}><sphereGeometry args={[0.12, 12, 10]} /><meshStandardMaterial color="#d6a589" /></mesh></group>
    <group ref={rightArm} position={[0.45, 1.5, 0]}><mesh position={[0, -0.34, 0]} castShadow><capsuleGeometry args={[0.13, 0.53, 4, 10]} /><meshStandardMaterial color={blouse} roughness={0.78} /></mesh><mesh position={[0, -0.67, 0.01]}><sphereGeometry args={[0.12, 12, 10]} /><meshStandardMaterial color="#d6a589" /></mesh></group>
  </group>;
}

function LoadedTeacher({ model, state, expression, viseme, walkTarget, lookTarget, reduced }: LoadedTeacherProps) {
  const outer = useRef<THREE.Group>(null);
  const mixer = useMemo(() => new AnimationMixer(model.scene), [model]);
  const { invalidate } = useThree();
  const fit = useMemo(() => {
    const bounds = new THREE.Box3().setFromObject(model.scene);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = size.y > 0 ? Math.min(2.85 / size.y, 4 / Math.max(size.x, size.z, 0.01)) : 1;
    return { scale, position: [-center.x * scale, -bounds.min.y * scale, -center.z * scale] as [number, number, number] };
  }, [model]);
  const humanoidBones = useMemo(() => {
    const found: Record<string, THREE.Bone> = {};
    model.scene.traverse(node => {
      const bone = node as THREE.Bone;
      if (!bone.isBone) return;
      const name = bone.name.toLowerCase().replace(/[^a-z]/g, "");
      if (/^(hips|pelvis)$/.test(name)) found.hips = bone;
      if (/^(head|headjoint)$/.test(name)) found.head = bone;
      if (/^(leftupperarm|upperarml|lupperarm|leftarm)$/.test(name)) found.leftArm = bone;
      if (/^(rightupperarm|upperarmr|rupperarm|rightarm)$/.test(name)) found.rightArm = bone;
      if (/^(leftupperleg|upperlegl|lupperleg|leftthigh)$/.test(name)) found.leftLeg = bone;
      if (/^(rightupperleg|upperlegr|rupperleg|rightthigh)$/.test(name)) found.rightLeg = bone;
    });
    return found;
  }, [model]);
  useEffect(() => {
    const clip = model.clips.find(item => item.name.toLowerCase().includes(state));
    mixer.stopAllAction();
    if (clip) mixer.clipAction(clip).reset().fadeIn(0.28).play();
    return () => { mixer.stopAllAction(); mixer.uncacheRoot(model.scene); };
  }, [mixer, model, state]);
  useEffect(() => {
    model.scene.traverse((node: Object3D) => {
      const mesh = node as THREE.Mesh;
      const dict = mesh.morphTargetDictionary;
      const influences = mesh.morphTargetInfluences;
      if (!dict || !influences) return;
      for (const [name, index] of Object.entries(dict)) {
        if (index === undefined) continue;
        const key = name.toLowerCase();
        const active = viseme !== "sil" && (key.includes(viseme) || (viseme === "aa" && (key.includes("open") || key.includes("jaw"))));
        const mood = expression === "neutral" ? false : key.includes(expression);
        influences[index] = active || mood ? 0.55 : 0;
      }
    });
    invalidate();
  }, [expression, invalidate, model, viseme]);
  const lastSyncViseme = useRef("");
  useFrame((_, delta) => {
    const clip = model.clips.find(item => item.name.toLowerCase().includes(state));
    mixer.update(reduced ? 0 : delta);
    const syncedViseme = immersiveVoiceBridge.getState() === "speaking" ? immersiveVoiceBridge.getFrame().viseme : "sil";
    if (syncedViseme !== lastSyncViseme.current) {
      lastSyncViseme.current = syncedViseme;
      model.scene.traverse((node: Object3D) => {
        const mesh = node as THREE.Mesh;
        const dict = mesh.morphTargetDictionary;
        const influences = mesh.morphTargetInfluences;
        if (!dict || !influences) return;
        for (const [name, index] of Object.entries(dict)) {
          if (index === undefined) continue;
          const key = name.toLowerCase();
          influences[index] = syncedViseme !== "sil" && (key.includes(syncedViseme) || (syncedViseme === "aa" && (key.includes("open") || key.includes("jaw")))) ? 0.55 : 0;
        }
      });
      invalidate();
    }
    if (reduced || clip || !outer.current) return;
    const time = performance.now() * 0.001;
    outer.current.position.y = Math.sin(time * 1.2) * 0.025;
    const yaw = state === "turn" ? Math.atan2(lookTarget[0] - outer.current.position.x, lookTarget[2] - outer.current.position.z) : 0;
    outer.current.rotation.y = THREE.MathUtils.damp(outer.current.rotation.y, yaw, 2.8, delta);
    const walking = state === "walk" ? Math.sin(time * 6) * 0.48 : 0;
    if (humanoidBones.leftLeg) humanoidBones.leftLeg.rotation.x = walking;
    if (humanoidBones.rightLeg) humanoidBones.rightLeg.rotation.x = -walking;
    if (humanoidBones.leftArm) humanoidBones.leftArm.rotation.x = -walking * 0.55;
    if (humanoidBones.rightArm) {
      const goal = state === "point" || state === "explain" || state === "celebrate" ? -0.85 : -walking * 0.55;
      humanoidBones.rightArm.rotation.x = THREE.MathUtils.damp(humanoidBones.rightArm.rotation.x, goal, 5, delta);
      humanoidBones.rightArm.rotation.z = THREE.MathUtils.damp(humanoidBones.rightArm.rotation.z, state === "celebrate" ? -0.85 : 0, 5, delta);
    }
    if (humanoidBones.leftArm) humanoidBones.leftArm.rotation.z = THREE.MathUtils.damp(humanoidBones.leftArm.rotation.z, state === "celebrate" ? 0.85 : 0, 5, delta);
    if (humanoidBones.head) humanoidBones.head.rotation.z = THREE.MathUtils.damp(humanoidBones.head.rotation.z, expression === "curious" ? -0.1 : 0, 3, delta);
    outer.current.position.x = THREE.MathUtils.damp(outer.current.position.x, walkTarget[0], state === "walk" ? 1.5 : 2.5, delta);
    outer.current.position.z = THREE.MathUtils.damp(outer.current.position.z, walkTarget[1], state === "walk" ? 1.5 : 2.5, delta);
  });
  return <group ref={outer} position={[-2, 0, -0.5]}><group scale={fit.scale} position={fit.position}><primitive object={model.scene} dispose={null} /></group></group>;
}

function disposeLoadedModel(model: LoadedModel) {
  model.scene.traverse(node => {
    const mesh = node as THREE.Mesh;
    mesh.geometry?.dispose();
    const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
    for (const material of materials) {
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose();
      material.dispose();
    }
  });
}

function Teacher(props: TeacherProps) {
  return props.model ? <LoadedTeacher state={props.state} expression={props.expression} viseme={props.viseme} walkTarget={props.walkTarget} lookTarget={props.lookTarget} reduced={props.reduced} model={props.model} /> : <PlaceholderTeacher state={props.state} expression={props.expression} target={props.target} walkTarget={props.walkTarget} lookTarget={props.lookTarget} viseme={props.viseme} reduced={props.reduced} />;
}

// Shared by the immersive scene; it reuses the prototype rendering contract
// without importing the preview room or its board-oriented controls.
export function ImmersiveTeacher({ state = "idle", reduced = false, voiceState = "idle" }: { state?: TeacherState; reduced?: boolean; voiceState?: ImmersiveVoiceState }) {
  const voiceTeacherState: TeacherState = voiceState === "listening" ? "listen"
    : voiceState === "speaking" || voiceState === "thinking" ? "explain"
      : state;
  return <Teacher state={voiceTeacherState} expression={voiceState === "thinking" ? "thinking" : "neutral"} target={null} walkTarget={[-2, -0.5]} lookTarget={[0, 1.5, -2]} viseme="sil" reduced={reduced} model={null} />;
}

function CameraRig({ cinematic }: { cinematic: boolean }) {
  const { camera } = useThree();
  useEffect(() => { camera.position.set(cinematic ? 0.4 : 1, 3, cinematic ? 8.4 : 10); camera.lookAt(0, 1.5, -2); }, [camera, cinematic]);
  return null;
}

export function TeacherPreview() {
  const [state, setState] = useState<TeacherState>("idle");
  const [expression, setExpression] = useState<Expression>("neutral");
  const [target, setTarget] = useState<BoardTarget | null>(null);
  const [walkTarget, setWalkTarget] = useState<[number, number]>([-2, -0.5]);
  const [lookTarget, setLookTarget] = useState<[number, number, number]>([0, 2.5, -6]);
  const [demoViseme, setDemoViseme] = useState("sil");
  const [demoRunning, setDemoRunning] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [sceneError, setSceneError] = useState(false);
  const [model, setModel] = useState<LoadedModel | null>(null);
  const [modelStatus, setModelStatus] = useState("No local character model loaded");
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [cinematic, setCinematic] = useState(true);
  const stageRef = useRef<HTMLElement>(null);
  const transitionTimer = useRef<number | undefined>(undefined);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)"), change = () => setReduced(media.matches);
    media.addEventListener("change", change); return () => media.removeEventListener("change", change);
  }, []);
  useEffect(() => () => { if (transitionTimer.current !== undefined) window.clearTimeout(transitionTimer.current); }, []);
  useEffect(() => () => { if (model) disposeLoadedModel(model); }, [model]);
  useEffect(() => {
    if (!demoRunning) { setDemoViseme("sil"); return; }
    const start = performance.now();
    const id = window.setInterval(() => {
      const timeline = validateVisemeTimeline(demoTimeline);
      const offset = (performance.now() - start) % 1250;
      setDemoViseme(visemeAt(timeline, offset));
    }, 70);
    return () => window.clearInterval(id);
  }, [demoRunning]);
  const runAction = useCallback((action: TeacherAction) => {
    const valid = validateTeacherAction(action);
    const transition = (next: TeacherState, durationMs: number) => {
      if (transitionTimer.current !== undefined) window.clearTimeout(transitionTimer.current);
      setState(next);
      transitionTimer.current = window.setTimeout(() => setState(current => current === next ? settledTeacherState(current) : current), durationMs);
    };
    switch (valid.type) {
      case "walkTo": setWalkTarget([valid.x, valid.z]); transition("walk", 1800); break;
      case "lookAt": setLookTarget([valid.x, valid.y, valid.z]); transition("turn", 1000); break;
      case "pointAt": setTarget(valid.target); transition("point", 1800); break;
      case "explain": transition("explain", valid.durationMs ?? 2600); break;
      case "gesture": transition(valid.name === "wave" ? "celebrate" : "explain", 1600); break;
      case "setExpression": setExpression(valid.expression); break;
      case "speak": setDemoRunning(true); break;
    }
  }, []);
  const fullscreenToggle = useCallback(async () => {
    if (!stageRef.current) return;
    if (!document.fullscreenElement) await stageRef.current.requestFullscreen?.(); else await document.exitFullscreen();
    setFullscreen(Boolean(document.fullscreenElement));
  }, []);
  useEffect(() => { const listener = () => setFullscreen(Boolean(document.fullscreenElement)); document.addEventListener("fullscreenchange", listener); return () => document.removeEventListener("fullscreenchange", listener); }, []);
  const loadLocalModel = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    if (!file.name.toLowerCase().endsWith(".glb")) { setModelStatus("Choose a single-file .glb model."); return; }
    setModelStatus("Loading local model…");
    try {
      const bytes = await file.arrayBuffer();
      const gltf = await new Promise<LoadedModel>((resolve, reject) => new GLTFLoader().parse(bytes, "", result => resolve({ scene: result.scene, clips: result.animations }), reject));
      setModel(gltf);
      const names: string[] = [];
      gltf.scene.traverse(node => { if ((node as THREE.SkinnedMesh).isSkinnedMesh) names.push("skinned mesh"); });
      setModelStatus(`${file.name} · ${names.length ? "skinned character" : "static model"} · ${gltf.clips.length} animation clips`);
    } catch { setModelStatus("Could not read that GLB. The geometric preview remains available."); }
    event.target.value = "";
  };
  const controls = <>
    <label className="tp-control">Animation<select value={state} onChange={event => setState(event.target.value as TeacherState)}>{states.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
    <label className="tp-control">Expression<select value={expression} onChange={event => { const value = event.target.value as Expression; setExpression(value); runAction({ type: "setExpression", expression: value }); }}>{expressions.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
  </>;
  return <main className="teacher-page">
    <header className="tp-header"><Link to="/" className="tp-brand">✦ BHASHA<span>LEARN</span><small> AI</small></Link><div className="tp-header-right"><span>ADV-05 · 3D TEACHER PREVIEW</span><Link to="/classroom">Text classroom ↗</Link></div></header>
    <section className="tp-intro"><div><span className="tp-kicker">YOUR FUTURISTIC CLASSROOM</span><h1>Meet your <span>AI teacher.</span></h1><p>Explore a real-time 3D classroom prototype. Load a locally licensed GLB character to preview its rig, clips, and facial morphs.</p></div><div className="tp-local-note"><b>AVATAR PREVIEW</b><span>{model ? "Local model loaded" : "Articulated geometric fallback"}</span></div></section>
    <section className="tp-layout">
      <section className="tp-stage-shell" ref={stageRef} aria-label="Interactive 3D classroom">
        {!sceneError ? <SceneErrorBoundary onError={() => setSceneError(true)}><Canvas shadows dpr={[1, 1.5]} camera={{ position: [0.4, 3, 8.4], fov: 42 }} gl={{ antialias: true, alpha: false, powerPreference: "low-power" }} frameloop={reduced ? "demand" : "always"} aria-label="Three dimensional classroom scene"><CameraRig cinematic={cinematic}/><Room/><Suspense fallback={null}><Teacher state={state} expression={expression} target={target} walkTarget={walkTarget} lookTarget={lookTarget} viseme={demoViseme} reduced={reduced} model={model}/></Suspense><OrbitControls makeDefault target={[0, 1.5, -2]} minDistance={5.5} maxDistance={13} minPolarAngle={0.45} maxPolarAngle={1.48} enablePan={false} /></Canvas></SceneErrorBoundary> : <div className="tp-webgl-fallback" role="alert"><strong>WebGL preview unavailable</strong><span>Enable WebGL in your browser or try a recent desktop browser.</span></div>}
        <div className="tp-stage-label"><i/> REAL-TIME 3D · {model ? "LOCAL AVATAR" : "PROTOTYPE AVATAR"}</div>
        <div className="tp-stage-actions"><button onClick={() => setCinematic(value => !value)} aria-pressed={cinematic}>Camera: {cinematic ? "Cinematic" : "Wide"}</button><button onClick={() => void fullscreenToggle()}>{fullscreen ? "Exit fullscreen" : "Fullscreen"}</button></div>
        <div className="tp-stage-caption" aria-live="polite">{state === "point" ? "Look at the highlighted board position" : `${expression} · ${state}`}</div>
      </section>
      <aside className="tp-panel" aria-label="Teacher controls">
        <div className="tp-panel-heading"><span className="tp-kicker">TEACHER STUDIO</span><h2>Direct the lesson</h2></div>
        <div className="tp-control-grid">{controls}</div>
        <div className="tp-control-block"><span className="tp-label">MOVEMENT</span><div className="tp-buttons"><button onClick={() => runAction({ type: "walkTo", x: 0, z: -0.5 })}>Walk</button><button onClick={() => runAction({ type: "lookAt", x: 0, y: 2, z: -5 })}>Turn to board</button><button onClick={() => runAction({ type: "explain", durationMs: 2600 })}>Explain</button><button onClick={() => runAction({ type: "gesture", name: "wave" })}>Celebrate</button></div></div>
        <div className="tp-control-block"><span className="tp-label">SMARTBOARD POINTING</span><label className="tp-control">Board position<select onChange={event => { const [x, y] = event.target.value.split(",").map(Number); runAction({ type: "pointAt", target: { x, y } }); }} defaultValue="0.72,0.34"><option value="0.72,0.34">Upper right · (0.72, 0.34)</option><option value="0.28,0.58">Center left · (0.28, 0.58)</option><option value="0.5,0.5">Center · (0.5, 0.5)</option></select></label></div>
        <div className="tp-control-block"><span className="tp-label">FACE & SPEECH FOUNDATION</span><button className="tp-demo-button" aria-pressed={demoRunning} onClick={() => { if (demoRunning) setDemoRunning(false); else runAction({ type: "speak", timeline: demoTimeline }); }}>{demoRunning ? "Stop synthetic viseme demo" : "Play synthetic viseme demo"}</button><small>Timed mouth-shape demo only; no audio or phoneme alignment.</small></div>
        <div className="tp-control-block tp-upload"><span className="tp-label">LOCAL AVATAR ASSET</span><label className="tp-upload-button">Choose GLB<input type="file" accept=".glb,model/gltf-binary" onChange={loadLocalModel}/></label><small>{modelStatus}</small><small>Use an asset you have rights to use. Nothing is downloaded remotely.</small></div>
        <label className="tp-motion-toggle"><input type="checkbox" checked={reduced} onChange={event => setReduced(event.target.checked)}/> Reduce motion</label>
      </aside>
    </section>
    <footer className="tp-footer"><span>Prototype avatar geometry is not a photorealistic character.</span><span>WebGL · local assets · bilingual-ready interaction contract</span></footer>
  </main>;
}
