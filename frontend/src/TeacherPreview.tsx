import { Component, Suspense, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ChangeEvent, type ErrorInfo, type ReactNode } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { AnimationMixer, type AnimationClip, type Group, type Object3D } from "three";
import { Link, useSearchParams } from "react-router-dom";
import { mapBoardTarget, settledTeacherState, teacherLessonSummary, validateTeacherAction, validateTeacherMode, validateVisemeTimeline, visemeAt, type BoardTarget, type Expression, type TeacherAction, type TeacherLessonContext, type TeacherMode, type TeacherState, type VisemeFrame } from "./teacherCore";
import { immersiveVoiceBridge, type ImmersiveVoiceState } from "./immersiveVoiceBridge";
import { getSharedSessionContext, type SharedSessionContext } from "./sessionContext";
import { getToken, request } from "./auth";
import { AvatarSyncController, type SyncLanguage } from "./avatarSync";
import { PhotoTeacher } from "./PhotoTeacher";
import { disposeTeacherPhoto, loadTeacherPhoto, type TeacherPhotoAsset } from "./teacherPhoto";
import { generateClassroomExplanation } from "./classroomTutor";
import "./teacher-preview.css";

const states: TeacherState[] = ["idle", "walk", "turn", "explain", "point", "listen", "celebrate"];
const expressions: Expression[] = ["neutral", "happy", "curious", "encouraging", "thinking"];
const demoTimeline: VisemeFrame[] = [{ atMs: 0, durationMs: 240, viseme: "aa" }, { atMs: 240, durationMs: 190, viseme: "ee" }, { atMs: 430, durationMs: 210, viseme: "mm" }, { atMs: 640, durationMs: 250, viseme: "oh" }, { atMs: 890, durationMs: 160, viseme: "fv" }, { atMs: 1050, durationMs: 200, viseme: "aa" }];

type TeacherProps = { state: TeacherState; expression: Expression; target: BoardTarget | null; walkTarget: [number, number]; lookTarget: [number, number, number]; viseme: string; reduced: boolean; model: LoadedModel | null; photo: TeacherPhotoAsset | null; mode: TeacherMode; voiceState: ImmersiveVoiceState };
type LoadedModel = { scene: Group; clips: AnimationClip[] };
type LoadedTeacherProps = Omit<TeacherProps, "target" | "model" | "photo" | "mode" | "voiceState"> & { model: LoadedModel };

class SceneErrorBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { this.props.onError(); }
  render() { return this.state.failed ? <div className="teacher-scene-error" role="alert">3D preview could not start in this browser. Try enabling WebGL or using a recent desktop browser.</div> : this.props.children; }
}

function Room({ mode }: { mode: TeacherMode }) {
  return <>
    <color attach="background" args={["#071329"]} />
    <fog attach="fog" args={["#071329", 12, 25]} />
    <ambientLight intensity={mode === "holographic" ? 0.62 : 0.85} color={mode === "holographic" ? "#b8d7ff" : "#ffe4cc"} />
    <directionalLight position={[-4, 7, 4]} intensity={mode === "holographic" ? 2.1 : 2.5} color={mode === "holographic" ? "#d7e9ff" : "#fff0dc"} castShadow />
    <pointLight position={[0, 4, -4]} intensity={mode === "holographic" ? 24 : 9} distance={13} color={mode === "holographic" ? "#25cfff" : "#ffc188"} />
    <pointLight position={[5, 3, 2]} intensity={mode === "holographic" ? 9 : 4} distance={9} color={mode === "holographic" ? "#a450ff" : "#7e8dcc"} />
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

function PlaceholderTeacher({ state, expression, target, walkTarget, lookTarget, viseme, reduced, mode }: Omit<TeacherProps, "model" | "photo">) {
  const root = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const clock = useRef(0);
  const pointing = useMemo(() => target ? mapBoardTarget(target) : [0, 2.4, -6] as [number, number, number], [target]);
  useFrame((_, delta) => {
    const syncedViseme = viseme;
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
  const blouse = mode === "holographic" ? "#77dff2" : "#f2d9cb";
  const skin = mode === "holographic" ? "#a9f5ff" : "#d6a589";
  const outfit = mode === "holographic" ? "#163a67" : "#56408b";
  return <group ref={root} position={[-2, 0, -0.5]}>
    {/* Clearly marked geometric prototype: production likeness requires a licensed skinned avatar. */}
    <mesh position={[0, 0.95, 0]} castShadow><capsuleGeometry args={[0.36, 0.7, 6, 12]} /><meshStandardMaterial color={outfit} roughness={0.62} emissive={mode === "holographic" ? "#1689d1" : "#000000"} emissiveIntensity={mode === "holographic" ? 0.65 : 0} /></mesh>
    <mesh position={[0, 1.45, 0]} castShadow><capsuleGeometry args={[0.42, 0.38, 5, 12]} /><meshStandardMaterial color={blouse} roughness={0.8} /></mesh>
    <mesh position={[-0.15, 0.31, 0]} castShadow><capsuleGeometry args={[0.13, 0.57, 4, 10]} /><meshStandardMaterial color="#242d4c" roughness={0.74} /></mesh>
    <mesh position={[0.15, 0.31, 0]} castShadow><capsuleGeometry args={[0.13, 0.57, 4, 10]} /><meshStandardMaterial color="#242d4c" roughness={0.74} /></mesh>
    <mesh position={[0, 1.78, 0]}><cylinderGeometry args={[0.12, 0.14, 0.22, 12]} /><meshStandardMaterial color={skin} roughness={0.76} /></mesh>
    <group ref={head} position={[0, 2.1, 0]}>
      <mesh castShadow><sphereGeometry args={[0.36, 24, 20]} /><meshStandardMaterial color={skin} roughness={0.62} emissive={mode === "holographic" ? "#1689d1" : "#000000"} emissiveIntensity={mode === "holographic" ? 0.35 : 0} /></mesh>
      <mesh position={[0, 0.17, -0.035]} castShadow><sphereGeometry args={[0.39, 24, 18]} /><meshStandardMaterial color="#302038" roughness={0.86} /></mesh>
      <mesh position={[0, 0.025, 0.315]}><sphereGeometry args={[0.3, 24, 18, 0, Math.PI * 2, 0.4, 2.1]} /><meshStandardMaterial color={skin} roughness={0.65} /></mesh>
      {[-0.12, 0.12].map(x => <mesh key={x} position={[x, 0.025, 0.308]}><sphereGeometry args={[0.025, 10, 8]} /><meshBasicMaterial color="#171b2c" /></mesh>)}
      <mesh ref={mouth} position={[0, -0.095, 0.32]}><capsuleGeometry args={[0.025, 0.055, 3, 6]} /><meshStandardMaterial color={viseme === "sil" ? "#734e4c" : "#6c3049"} /></mesh>
      <mesh position={[0, 0.13, 0.05]}><sphereGeometry args={[0.19, 16, 12, 0, Math.PI * 2, 0, 1.5]} /><meshStandardMaterial color={expression === "happy" || expression === "encouraging" ? "#392037" : "#302038"} roughness={0.7} /></mesh>
    </group>
    <group ref={leftArm} position={[-0.45, 1.5, 0]}><mesh position={[0, -0.34, 0]} rotation={[0, 0, 0.12]} castShadow><capsuleGeometry args={[0.13, 0.53, 4, 10]} /><meshStandardMaterial color={blouse} roughness={0.78} /></mesh><mesh position={[0, -0.67, 0.01]}><sphereGeometry args={[0.12, 12, 10]} /><meshStandardMaterial color={skin} /></mesh></group>
    <group ref={rightArm} position={[0.45, 1.5, 0]}><mesh position={[0, -0.34, 0]} castShadow><capsuleGeometry args={[0.13, 0.53, 4, 10]} /><meshStandardMaterial color={blouse} roughness={0.78} /></mesh><mesh position={[0, -0.67, 0.01]}><sphereGeometry args={[0.12, 12, 10]} /><meshStandardMaterial color={skin} /></mesh></group>
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
    const syncedViseme = viseme;
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
          const speaking = syncedViseme !== "sil" && (key.includes(syncedViseme) || (syncedViseme === "aa" && (key.includes("open") || key.includes("jaw"))));
          const mood = expression !== "neutral" && key.includes(expression);
          influences[index] = speaking || mood ? 0.55 : 0;
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

function HologramProjection() {
  return <group position={[-2, 0, -0.5]}>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.025, 0]}><ringGeometry args={[0.48, 0.53, 64]} /><meshBasicMaterial color="#5beaff" transparent opacity={0.78} /></mesh>
    <mesh position={[0, 1.55, 0]}><cylinderGeometry args={[0.56, 0.56, 2.85, 32, 1, true]} /><meshBasicMaterial color="#56dfff" wireframe transparent opacity={0.12} depthWrite={false} /></mesh>
    <mesh position={[0, 2.92, 0]} rotation={[Math.PI / 2, 0, 0]}><ringGeometry args={[0.43, 0.48, 48]} /><meshBasicMaterial color="#9a7aff" transparent opacity={0.72} /></mesh>
  </group>;
}

function Teacher(props: TeacherProps) {
  const bridgeState = useSyncExternalStore(immersiveVoiceBridge.subscribe, immersiveVoiceBridge.getState, () => "idle" as ImmersiveVoiceState);
  const frame = useSyncExternalStore(immersiveVoiceBridge.subscribeFrames, immersiveVoiceBridge.getFrame, () => ({ generation: 0, state: "idle" as const, mode: "silent" as const, language: "mixed" as const, currentTimeMs: 0, viseme: "sil" as const }));
  const voiceState = bridgeState !== "idle" ? bridgeState : props.voiceState;
  const viseme = voiceState === "speaking" ? frame.viseme ?? immersiveVoiceBridge.getFrame().viseme : props.viseme;
  const voiceTeacherState: TeacherState = voiceState === "listening" ? "listen" : voiceState === "speaking" || voiceState === "thinking" ? "explain" : props.state;
  const expression = voiceState === "thinking" ? "thinking" : props.expression;
  return <>
    {props.photo ? <PhotoTeacher photo={props.photo} mode={props.mode} /> : props.model ? <LoadedTeacher state={voiceTeacherState} expression={expression} viseme={viseme} walkTarget={props.walkTarget} lookTarget={props.lookTarget} reduced={props.reduced} model={props.model} /> : <PlaceholderTeacher state={voiceTeacherState} expression={expression} target={props.target} walkTarget={props.walkTarget} lookTarget={props.lookTarget} viseme={viseme} reduced={props.reduced} mode={props.mode} voiceState={voiceState} />}
    {props.mode === "holographic" && <HologramProjection />}
  </>;
}

// Shared by the immersive scene; it reuses the prototype rendering contract
// without importing the preview room or its board-oriented controls.
export function ImmersiveTeacher({ state = "idle", reduced = false, voiceState = "idle", mode = "holographic" }: { state?: TeacherState; reduced?: boolean; voiceState?: ImmersiveVoiceState; mode?: TeacherMode }) {
  return <Teacher state={state} expression={voiceState === "thinking" ? "thinking" : "neutral"} target={null} walkTarget={[-2, -0.5]} lookTarget={[0, 1.5, -2]} viseme="sil" reduced={reduced} model={null} photo={null} mode={mode} voiceState={voiceState} />;
}

function CameraRig({ cinematic }: { cinematic: boolean }) {
  const { camera } = useThree();
  useEffect(() => { camera.position.set(cinematic ? 0.4 : 1, 3, cinematic ? 8.4 : 10); camera.lookAt(0, 1.5, -2); }, [camera, cinematic]);
  return null;
}

export function TeacherPreview({ sessionId }: { sessionId?: string } = {}) {
  const [params, setParams] = useSearchParams();
  const activeSessionId = sessionId || params.get("session") || "";
  const originalQuestion = params.get("question") || "";
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
  const [photoAsset,setPhotoAsset]=useState<TeacherPhotoAsset|null>(null),[photoPermission,setPhotoPermission]=useState(false),[photoError,setPhotoError]=useState(""),[photoBusy,setPhotoBusy]=useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [cinematic, setCinematic] = useState(true);
  const [mode, setMode] = useState<TeacherMode>(() => params.get("mode") === "holographic" ? "holographic" : "realistic");
  const [lessonContext, setLessonContext] = useState<SharedSessionContext | null>(null);
  const [contextError, setContextError] = useState("");
  const [lessonAnswer, setLessonAnswer] = useState("");
  const [lessonBusy, setLessonBusy] = useState(false);
  const [lessonError, setLessonError] = useState("");
  const [followup, setFollowup] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [speechBusy, setSpeechBusy] = useState(false);
  const [audioPlaying,setAudioPlaying]=useState(false);
  const [language, setLanguage] = useState<SyncLanguage>("mixed");
  const audioRef = useRef<HTMLAudioElement>(null);
  const syncGeneration = useRef<number | null>(null);
  const speechAbort = useRef<AbortController | null>(null);
  const syncController = useRef(new AvatarSyncController(frame => immersiveVoiceBridge.acceptFrame(frame)));
  const stageRef = useRef<HTMLElement>(null);
  const transitionTimer = useRef<number | undefined>(undefined);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)"), change = () => setReduced(media.matches);
    media.addEventListener("change", change); return () => media.removeEventListener("change", change);
  }, []);
  useEffect(() => () => { if (transitionTimer.current !== undefined) window.clearTimeout(transitionTimer.current); }, []);
  useEffect(() => () => { if (model) disposeLoadedModel(model); }, [model]);
  useEffect(() => () => { if (photoAsset) disposeTeacherPhoto(photoAsset); }, [photoAsset]);
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl); }, [audioUrl]);
  useEffect(() => {
    let active = true;
    setLessonContext(null);
    setContextError("");
    if (!activeSessionId) return () => { active = false; };
    getSharedSessionContext(activeSessionId).then(context => { if (active) { setLessonContext(context); setLanguage(context.preferred_language); } }).catch(cause => {
      if (active) setContextError(cause instanceof Error ? cause.message : "Shared lesson context is unavailable.");
    });
    return () => { active = false; };
  }, [activeSessionId]);
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
  useEffect(() => { runAction({ type: "walkTo", x: -1.6, z: -0.5 }); }, [runAction]);
  const stopSpeech = useCallback(() => {
    speechAbort.current?.abort(); speechAbort.current = null;
    const element = audioRef.current;
    if (element) { element.pause(); element.currentTime = 0; }
    if (syncGeneration.current !== null) syncController.current.cancel(syncGeneration.current);
    setAudioPlaying(false);
    syncGeneration.current = null;
    immersiveVoiceBridge.setState("idle");
    setAudioUrl("");
    setSpeechBusy(false);
    setState("idle");
  }, []);
  async function startSpeech(text: string) {
    if (!activeSessionId) { setLessonError("Open this classroom from a saved chat session to generate speech."); return; }
    stopSpeech(); setSpeechBusy(true); immersiveVoiceBridge.setState("thinking");
    const controller = new AbortController(); speechAbort.current = controller;
    try {
      const response = await fetch(`/api/v1/voice/sessions/${encodeURIComponent(activeSessionId)}/speech`, {
        method: "POST", headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }), signal: controller.signal,
      });
      if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail || "Speech generation failed."); }
      setAudioUrl(URL.createObjectURL(await response.blob()));
    } catch (cause) {
      if (controller.signal.aborted) return;
      immersiveVoiceBridge.setState("error");
      setLessonError(cause instanceof Error ? `Explanation is saved as text. Speech is unavailable: ${cause.message}` : "Explanation is saved as text. Speech is unavailable.");
    } finally { if (speechAbort.current === controller) speechAbort.current = null; setSpeechBusy(false); }
  }
  async function askTeacher(message: string) {
    if (!activeSessionId || lessonBusy || !message.trim()) return;
    setLessonBusy(true); setLessonError(""); setState("explain"); immersiveVoiceBridge.setState("thinking");
    try {
      const send = (sessionId: string, text: string) => request<{ reply: string }>(`/tutor/sessions/${encodeURIComponent(sessionId)}/chat`, {
        method: "POST", headers: { Authorization: `Bearer ${getToken()}` }, body: JSON.stringify({ message: text }),
      });
      const result = originalQuestion && !lessonAnswer
        ? await generateClassroomExplanation({ sessionId: activeSessionId, question: originalQuestion, language, learningLevel: lessonContext?.learning_level || "beginner" }, send)
        : await send(activeSessionId, message);
      setLessonAnswer(result.reply);
      setState("point");
      setTarget({ x: 0.72, y: 0.34 });
      void startSpeech(result.reply);
    } catch (cause) {
      immersiveVoiceBridge.setState("idle");
      setState("idle");
      setLessonError(cause instanceof Error ? cause.message : "The classroom could not generate an explanation. Your original doubt is still available.");
    } finally { setLessonBusy(false); }
  }
  async function changeLanguage(value: SyncLanguage) {
    setLanguage(value);
    if (!getToken()) return;
    try {
      await request("/students/me/preferences", { method: "PUT", headers: { Authorization: `Bearer ${getToken()}` }, body: JSON.stringify({ preferred_language: value, learning_level: lessonContext?.learning_level || "beginner", learning_pace: lessonContext?.learning_pace || "steady", learning_goal: lessonContext?.learning_goal || null }) });
    } catch (cause) {
      setLessonError(cause instanceof Error ? `Language changed for this lesson, but the preference could not be saved: ${cause.message}` : "Language preference could not be saved.");
    }
  }
  function beginPlayback() {
    const generation = syncController.current.begin({}, language);
    syncGeneration.current = generation;
    syncController.current.play(generation);
    setAudioPlaying(true);
    immersiveVoiceBridge.setState("speaking");
    setState("explain");
  }
  function pausePlayback() {
    if (syncGeneration.current !== null) syncController.current.pause(syncGeneration.current);
    setAudioPlaying(false);
    immersiveVoiceBridge.setState("paused");
    setState("idle");
  }
  function updatePlayback() {
    const element = audioRef.current;
    if (element && syncGeneration.current !== null) syncController.current.tick(syncGeneration.current, { currentTime: element.currentTime, paused: element.paused, ended: element.ended, duration: element.duration });
  }
  function finishPlayback() {
    if (syncGeneration.current !== null) syncController.current.complete(syncGeneration.current);
    setAudioPlaying(false);
    syncGeneration.current = null;
    immersiveVoiceBridge.setState("idle");
    setState("idle");
  }
  function selectMode(value: TeacherMode) {
    setMode(validateTeacherMode(value));
    setParams(current => { const next = new URLSearchParams(current); next.set("mode", value); return next; });
  }
  const fullscreenToggle = useCallback(async () => {
    if (!stageRef.current) return;
    if (!document.fullscreenElement) await stageRef.current.requestFullscreen?.(); else await document.exitFullscreen();
    setFullscreen(Boolean(document.fullscreenElement));
  }, []);
  useEffect(() => { const listener = () => setFullscreen(Boolean(document.fullscreenElement)); document.addEventListener("fullscreenchange", listener); return () => document.removeEventListener("fullscreenchange", listener); }, []);
  const loadPhoto=async(event:ChangeEvent<HTMLInputElement>)=>{const file=event.target.files?.[0];event.target.value="";if(!file)return;setPhotoError("");setPhotoBusy(true);try{setPhotoAsset(await loadTeacherPhoto(file,photoPermission))}catch(cause){setPhotoError(cause instanceof Error?cause.message:"Image preview failed.")}finally{setPhotoBusy(false)}};
  const removePhoto=()=>{setPhotoAsset(null);setPhotoError("")};
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
  const lesson = teacherLessonSummary(lessonContext as TeacherLessonContext | null);
  const controls = <>
    <label className="tp-control">Animation<select disabled={Boolean(photoAsset)} value={state} onChange={event => setState(event.target.value as TeacherState)}>{states.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
    <label className="tp-control">Expression<select disabled={Boolean(photoAsset)} value={expression} onChange={event => { const value = event.target.value as Expression; setExpression(value); runAction({ type: "setExpression", expression: value }); }}>{expressions.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
  </>;
  const lessonControls = <section className="tp-live-lesson" aria-label="Interactive lesson controls">
    <span className="tp-label">CLASSROOM EXPLANATION</span>
    {originalQuestion ? <blockquote><b>Student doubt</b><br/>{originalQuestion}</blockquote> : <p>Ask a doubt from chat, then open this classroom to keep its full context.</p>}
    {!lessonAnswer && <button className="tp-primary-action" type="button" disabled={!activeSessionId || lessonBusy || !originalQuestion} onClick={() => void askTeacher(originalQuestion)}>Start explanation</button>}
    {(lessonBusy || speechBusy) && <p className="tp-live-status" role="status">{lessonBusy ? "Teacher is thinking…" : "Generating Gnani speech…"}</p>}
    {lessonAnswer && <div className="tp-lesson-answer"><strong>Lesson explanation</strong><p>{lessonAnswer}</p></div>}
    {audioUrl && <div className="tp-audio-controls"><audio ref={audioRef} src={audioUrl} onPlay={beginPlayback} onPause={event => { if (!event.currentTarget.ended) pausePlayback(); }} onTimeUpdate={updatePlayback} onEnded={finishPlayback} onError={() => { finishPlayback(); setLessonError("Audio playback failed. The text explanation is still available."); }}>Audio playback unavailable.</audio><button type="button" onClick={() => audioRef.current?.paused ? void audioRef.current.play() : audioRef.current?.pause()}>{audioRef.current?.paused ? "Resume" : "Pause / resume"}</button><button type="button" onClick={() => void startSpeech(lessonAnswer)}>Repeat</button><button type="button" onClick={stopSpeech}>Stop</button></div>}
    <label className="tp-control">Explanation language<select value={language} disabled={lessonBusy} onChange={event => void changeLanguage(event.target.value as SyncLanguage)}><option value="mixed">Telugu + English</option><option value="english">English</option><option value="telugu">తెలుగు</option></select></label>
    {lessonAnswer && <form className="tp-followup" onSubmit={event => { event.preventDefault(); const text = followup.trim(); if (!text) return; setFollowup(""); void askTeacher(text); }}><label htmlFor="tp-followup">Ask another doubt</label><div><input id="tp-followup" value={followup} onFocus={() => setState("listen")} onChange={event => setFollowup(event.target.value)} placeholder="Ask a follow-up question"/><button type="submit" disabled={lessonBusy || !followup.trim()}>Ask</button></div></form>}
    {lessonError && <p role="alert" className="tp-lesson-error">{lessonError}</p>}
    {audioUrl&&!photoAsset&&<small>Approximate audio-timed mouth motion; no phoneme alignment is available. Compatible rigged face targets are required.</small>}{audioUrl&&photoAsset&&<small>Speech is indicated on screen; a static photograph has no mouth animation.</small>}
  </section>;
  return <main className="teacher-page">
    <header className="tp-header"><Link to="/" className="tp-brand">✦ BHASHA<span>LEARN</span><small> AI</small></Link><div className="tp-header-right"><span>INTERACTIVE CLASSROOM · {lessonContext?.topic || "Loading session"}</span><Link to={activeSessionId ? `/chat?session=${encodeURIComponent(activeSessionId)}` : "/chat"}>Return to chat ↗</Link></div></header>
    <section className="tp-intro"><div><span className="tp-kicker">YOUR AI CLASSROOM</span><h1>Meet your <span>AI teacher.</span></h1><p>Choose a browser-local photo for a static teacher appearance, or a compatible rigged local model for supported movement and approximate face cues. Articulated geometric fallback available. Switch to hologram styling at any time.</p></div><div className="tp-local-note"><b>{mode === "realistic" ? "HUMAN TEACHER" : "HOLOGRAPHIC TEACHER"}</b><span>{photoAsset ? "Selected photo · browser-local" : model ? "Locally loaded character" : "Licensed rigged human asset needed"}</span></div></section>
    <section className="tp-layout">
      <section className={`tp-stage-shell tp-stage-${mode}`} ref={stageRef} aria-label="Interactive 3D classroom">
        {!sceneError ? <SceneErrorBoundary onError={() => setSceneError(true)}><Canvas shadows dpr={[1, 1.5]} camera={{ position: [0.4, 3, 8.4], fov: 42 }} gl={{ antialias: true, alpha: false, powerPreference: "low-power" }} frameloop={reduced ? "demand" : "always"} aria-label="Three dimensional classroom scene"><CameraRig cinematic={cinematic}/><Room mode={mode}/><Suspense fallback={null}><Teacher state={state} expression={expression} target={target} walkTarget={walkTarget} lookTarget={lookTarget} viseme={demoViseme} reduced={reduced} model={model} photo={photoAsset} mode={mode} voiceState="idle"/></Suspense><OrbitControls makeDefault target={[0, 1.5, -2]} minDistance={5.5} maxDistance={13} minPolarAngle={0.45} maxPolarAngle={1.48} enablePan={false} /></Canvas></SceneErrorBoundary> : <div className="tp-webgl-fallback" role="alert"><strong>WebGL preview unavailable</strong><span>Enable WebGL in your browser or try a recent desktop browser.</span></div>}
        <div className="tp-stage-label"><i/> {mode === "holographic" ? "HOLOGRAPHIC CLASSROOM" : "HUMAN TEACHER CLASSROOM"} · {photoAsset ? "BROWSER-LOCAL PHOTO" : model ? "LOCAL RIG" : "GEOMETRIC FALLBACK"}</div>
        {photoAsset && audioPlaying && <div className="tp-photo-speaking" role="status" aria-live="polite"><i/>Teacher speech playing · photograph is static</div>}
        <div className="tp-stage-actions"><button onClick={() => setCinematic(value => !value)} aria-pressed={cinematic}>Camera: {cinematic ? "Cinematic" : "Wide"}</button><button onClick={() => void fullscreenToggle()}>{fullscreen ? "Exit fullscreen" : "Fullscreen"}</button></div>
        <div className="tp-stage-caption" aria-live="polite">{photoAsset ? (audioPlaying ? "Photo teacher - speaking" : "Photo teacher - static appearance") : state === "point" ? "Look at the highlighted board position" : expression + " · " + state}</div>
      </section>
      <aside className="tp-panel" aria-label="Teacher controls">
        <div className="tp-panel-heading"><span className="tp-kicker">TEACHER STUDIO</span><h2>Direct the lesson</h2></div>
        <div className="tp-mode-picker" role="group" aria-label="Teacher presentation mode">
          <button type="button" aria-pressed={mode === "realistic"} onClick={() => selectMode("realistic")}><strong>Human teacher</strong><span>Animated preview; rigged asset required for realistic identity</span></button>
          <button type="button" aria-pressed={mode === "holographic"} onClick={() => selectMode("holographic")}><strong>Holographic teacher</strong><span>Blue/cyan hologram projection</span></button>
        </div>
        <section className="tp-lesson-context" aria-label="Shared lesson context">
          <span className="tp-label">SHARED LESSON</span>
          <strong>{lesson.title}</strong>
          <p>{lesson.detail}</p>
          {lessonContext && <small>{lesson.language} · {lesson.level}</small>}
          {!lessonContext && <small role={contextError ? "alert" : "status"}>{contextError || (activeSessionId ? "Loading shared session…" : "Connect a session to load its lesson context.")}</small>}
        </section>
        {lessonControls}
        <div className="tp-control-grid">{controls}</div>
        <div className="tp-control-block"><span className="tp-label">MOVEMENT & GESTURES</span>{photoAsset?<small role="note">Static photograph: movement and gestures require a compatible rigged GLB.</small>:<div className="tp-buttons"><button onClick={() => runAction({ type: "walkTo", x: 0, z: -0.5 })}>Walk</button><button onClick={() => runAction({ type: "lookAt", x: 0, y: 2, z: -5 })}>Turn to board</button><button onClick={() => runAction({ type: "explain", durationMs: 2600 })}>Explain</button><button onClick={() => runAction({ type: "gesture", name: "wave" })}>Celebrate</button></div>}</div>
        {!photoAsset && (<div className="tp-control-block"><span className="tp-label">SMARTBOARD POINTING</span><label className="tp-control">Board position<select onChange={event => { const [x, y] = event.target.value.split(",").map(Number); runAction({ type: "pointAt", target: { x, y } }); }} defaultValue="0.72,0.34"><option value="0.72,0.34">Upper right · (0.72, 0.34)</option><option value="0.28,0.58">Center left · (0.28, 0.58)</option><option value="0.5,0.5">Center · (0.5, 0.5)</option></select></label></div>)}
        {!photoAsset && (<div className="tp-control-block"><span className="tp-label">FACE & SPEECH FOUNDATION</span><button className="tp-demo-button" aria-pressed={demoRunning} onClick={() => { if (demoRunning) setDemoRunning(false); else runAction({ type: "speak", timeline: demoTimeline }); }}>{demoRunning ? "Stop synthetic viseme demo" : "Play synthetic viseme demo"}</button><small>Timed mouth-shape demo only; no audio or phoneme alignment.</small></div>)}
        <section className="tp-control-block tp-upload tp-photo-upload" aria-label="Photo teacher">
          <span className="tp-label">PHOTO-BASED HUMAN TEACHER</span>
          <label className="tp-photo-consent"><input type="checkbox" checked={photoPermission} onChange={event=>{setPhotoPermission(event.target.checked);if(!event.target.checked)removePhoto()}}/> I have permission to use this person's likeness.</label>
          <label className="tp-upload-button">Choose full-body photo<input type="file" accept="image/png,image/jpeg,image/webp" aria-label="Choose full-body teacher photo" disabled={!photoPermission||photoBusy} onChange={loadPhoto}/></label>
          {photoBusy&&<small role="status">Checking and previewing photo…</small>}
          {photoAsset&&<div className="tp-photo-preview"><img src={photoAsset.previewUrl} alt={"Selected teacher photo: "+photoAsset.name}/><div><strong>{photoAsset.name}</strong><small>{photoAsset.width} x {photoAsset.height} · stays in this browser</small><button type="button" onClick={removePhoto}>Remove photo</button></div></div>}
          {photoError&&<p className="tp-photo-error" role="alert">{photoError}</p>}
          <small>Photo stays in this browser and is never sent to Gemini or Gnani. It is static; use a rigged GLB for movement or approximate mouth cues.</small>
        </section>
        <div className="tp-control-block tp-upload"><span className="tp-label">OPTIONAL RIGGED AVATAR</span><label className="tp-upload-button">Choose GLB<input type="file" accept=".glb,model/gltf-binary" onChange={loadLocalModel}/></label><small>{modelStatus}</small><small>Photo takes visual priority. Removing it returns to the GLB or geometric fallback. Use only authorized assets.</small></div>
        <label className="tp-motion-toggle"><input type="checkbox" checked={reduced} onChange={event => setReduced(event.target.checked)}/> Reduce motion</label>
      </aside>
    </section>
    <footer className="tp-footer"><span>Prototype avatar geometry is not a photorealistic character.</span><span>WebGL · local assets · bilingual-ready interaction contract</span></footer>
  </main>;
}
