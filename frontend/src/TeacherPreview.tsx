import { Component, Suspense, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ChangeEvent, type ErrorInfo, type ReactNode } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { AnimationMixer, type AnimationClip, type Group, type Object3D } from "three";
import { Link } from "react-router-dom";
import { SessionModeNav } from "./SessionModeNav";
import { settledTeacherState, teacherLessonSummary, validateTeacherAction, type BoardTarget, type Expression, type TeacherAction, type TeacherLessonContext, type TeacherMode, type TeacherState } from "./teacherCore";
import { immersiveVoiceBridge, type ImmersiveVoiceState } from "./immersiveVoiceBridge";
import { getSharedSessionContext, type SharedSessionContext } from "./sessionContext";
import { disposeTeacherPhoto, loadTeacherPhoto, type TeacherPhotoAsset } from "./teacherPhoto";
import "./teacher-preview.css";

const states: TeacherState[] = ["idle", "walk", "turn", "explain", "point", "listen", "celebrate"];
const expressions: Expression[] = ["neutral", "happy", "curious", "encouraging", "thinking"];

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

function Teacher(props: TeacherProps) {
  const bridgeState = useSyncExternalStore(immersiveVoiceBridge.subscribe, immersiveVoiceBridge.getState, () => "idle" as ImmersiveVoiceState);
  const frame = useSyncExternalStore(immersiveVoiceBridge.subscribeFrames, immersiveVoiceBridge.getFrame, () => ({ generation: 0, state: "idle" as const, mode: "silent" as const, language: "mixed" as const, currentTimeMs: 0, viseme: "sil" as const }));
  const voiceState = bridgeState !== "idle" ? bridgeState : props.voiceState;
  const viseme = voiceState === "speaking" ? frame.viseme ?? immersiveVoiceBridge.getFrame().viseme : props.viseme;
  const voiceTeacherState: TeacherState = voiceState === "listening" ? "listen" : voiceState === "speaking" || voiceState === "thinking" ? "explain" : props.state;
  const expression = voiceState === "thinking" ? "thinking" : props.expression;
  // Render only a supplied rigged character. A flat photo or geometric
  // prototype is not presented as a realistic human teacher.
  return props.model ? <LoadedTeacher state={voiceTeacherState} expression={expression} viseme={viseme} walkTarget={props.walkTarget} lookTarget={props.lookTarget} reduced={props.reduced} model={props.model} /> : null;
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
  const [state, setState] = useState<TeacherState>("idle");
  const [expression, setExpression] = useState<Expression>("neutral");
  const [target, setTarget] = useState<BoardTarget | null>(null);
  const [walkTarget, setWalkTarget] = useState<[number, number]>([-2, -0.5]);
  const [lookTarget, setLookTarget] = useState<[number, number, number]>([0, 2.5, -6]);
  const [fullscreen, setFullscreen] = useState(false);
  const [sceneError, setSceneError] = useState(false);
  const [model, setModel] = useState<LoadedModel | null>(null);
  const [modelStatus, setModelStatus] = useState("No local character model loaded");
  const [photoAsset, setPhotoAsset] = useState<TeacherPhotoAsset | null>(null);
  const [photoPermission, setPhotoPermission] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const [photoBusy, setPhotoBusy] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [cinematic, setCinematic] = useState(true);
  const mode: TeacherMode = "realistic";
  const [lessonContext, setLessonContext] = useState<SharedSessionContext | null>(null);
  const [contextError, setContextError] = useState("");
  const stageRef = useRef<HTMLElement>(null);
  const transitionTimer = useRef<number | undefined>(undefined);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)"), change = () => setReduced(media.matches);
    media.addEventListener("change", change); return () => media.removeEventListener("change", change);
  }, []);
  useEffect(() => () => { if (transitionTimer.current !== undefined) window.clearTimeout(transitionTimer.current); }, []);
  useEffect(() => () => { if (model) disposeLoadedModel(model); }, [model]);
  useEffect(() => () => { if (photoAsset) disposeTeacherPhoto(photoAsset); }, [photoAsset]);
  useEffect(() => {
    let active = true;
    setLessonContext(null);
    setContextError("");
    if (!sessionId) return () => { active = false; };
    getSharedSessionContext(sessionId).then(context => { if (active) setLessonContext(context); }).catch(cause => {
      if (active) setContextError(cause instanceof Error ? cause.message : "Shared lesson context is unavailable.");
    });
    return () => { active = false; };
  }, [sessionId]);
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
      case "speak": transition("explain", valid.timeline.reduce((end, frame) => Math.max(end, frame.atMs + frame.durationMs), 0)); break;
    }
  }, []);
  const fullscreenToggle = useCallback(async () => {
    if (!stageRef.current) return;
    if (!document.fullscreenElement) await stageRef.current.requestFullscreen?.(); else await document.exitFullscreen();
    setFullscreen(Boolean(document.fullscreenElement));
  }, []);
  useEffect(() => { const listener = () => setFullscreen(Boolean(document.fullscreenElement)); document.addEventListener("fullscreenchange", listener); return () => document.removeEventListener("fullscreenchange", listener); }, []);
  const loadPhoto = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setPhotoError("");
    setPhotoBusy(true);
    try { setPhotoAsset(await loadTeacherPhoto(file, photoPermission)); }
    catch (cause) { setPhotoError(cause instanceof Error ? cause.message : "Image preview failed."); }
    finally { setPhotoBusy(false); }
  };
  const removePhoto = () => { setPhotoAsset(null); setPhotoError(""); };
  const loadLocalModel = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    if (!file.name.toLowerCase().endsWith(".glb")) { setModelStatus("Choose a single-file .glb model."); return; }
    setModelStatus("Loading local model…");
    try {
      const bytes = await file.arrayBuffer();
      const gltf = await new Promise<LoadedModel>((resolve, reject) => new GLTFLoader().parse(bytes, "", result => resolve({ scene: result.scene, clips: result.animations }), reject));
      const names: string[] = [];
      gltf.scene.traverse(node => { if ((node as THREE.SkinnedMesh).isSkinnedMesh) names.push("skinned mesh"); });
      if (!names.length) {
        disposeLoadedModel(gltf);
        setModelStatus("This GLB has no rigged/skinned character. Choose a licensed rigged human avatar.");
        return;
      }
      setModel(gltf);
      setModelStatus(`${file.name} · skinned character · ${gltf.clips.length} animation clips`);
    } catch { setModelStatus("Could not read that GLB. The human avatar remains unavailable."); }
    event.target.value = "";
  };
  const lesson = teacherLessonSummary(lessonContext as TeacherLessonContext | null);
  const boardReply = lessonContext?.messages.filter(message => message.role === "assistant").at(-1);
  const boardQuestion = lessonContext?.messages.filter(message => message.role === "user").at(-1);
  const controls = <>
    <label className="tp-control">Animation<select disabled={!model || Boolean(photoAsset)} value={state} onChange={event => setState(event.target.value as TeacherState)}>{states.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
    <label className="tp-control">Expression<select disabled={!model || Boolean(photoAsset)} value={expression} onChange={event => { const value = event.target.value as Expression; setExpression(value); runAction({ type: "setExpression", expression: value }); }}>{expressions.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
  </>;
  return <main className="teacher-page">
    <header className="tp-header"><Link to="/" className="tp-brand">✦ BHASHA<span>LEARN</span><small> AI</small></Link><div className="tp-header-right"><span>ADV-05 · 3D TEACHER PREVIEW</span><SessionModeNav sessionId={sessionId} active="teacher"/><Link to={sessionId ? `/classroom?session=${encodeURIComponent(sessionId)}` : "/classroom"}>Text classroom ↗</Link></div></header>
    <section className="tp-intro"><div><span className="tp-kicker">YOUR AI CLASSROOM</span><h1>AI classroom</h1><p>Ask a question and receive a live tutor explanation with lesson context. A realistic animated human needs a licensed rigged character asset; a single photo cannot provide full-body movement or accurate lip sync.</p></div><div className="tp-local-note"><b>HUMAN AVATAR</b><span>{model ? modelStatus : "No rigged human asset loaded"}</span></div></section>
    <section className="tp-layout">
      <section className="tp-stage-shell tp-stage-realistic" ref={stageRef} aria-label="Interactive classroom">
        {!sceneError ? <SceneErrorBoundary onError={() => setSceneError(true)}><Canvas shadows dpr={[1, 1.5]} camera={{ position: [0.4, 3, 8.4], fov: 42 }} gl={{ antialias: true, alpha: false, powerPreference: "low-power" }} frameloop={reduced ? "demand" : "always"} aria-label="Three dimensional classroom scene"><CameraRig cinematic={cinematic}/><Room mode={mode}/><Suspense fallback={null}><Teacher state={state} expression={expression} target={target} walkTarget={walkTarget} lookTarget={lookTarget} viseme="sil" reduced={reduced} model={model} photo={photoAsset} mode={mode} voiceState="idle"/></Suspense><OrbitControls makeDefault target={[0, 1.5, -2]} minDistance={5.5} maxDistance={13} minPolarAngle={0.45} maxPolarAngle={1.48} enablePan={false} /></Canvas></SceneErrorBoundary> : <div className="tp-webgl-fallback" role="alert"><strong>WebGL preview unavailable</strong><span>Enable WebGL in your browser or try a recent desktop browser.</span></div>}
        <div className="tp-stage-board" aria-label="Live smartboard content"><span>LIVE LESSON BOARD · {lessonContext?.preferred_language || "SESSION"}</span><h2>{lesson.title}</h2>{boardQuestion && <small>Student: {boardQuestion.content}</small>}{boardReply ? <article>{boardReply.content}</article> : <p>Ask a question in the live tutor to write its explanation here.</p>}</div>
        {!model && <div className="tp-avatar-unavailable" role="status"><strong>Realistic teacher asset not configured</strong><span>Upload a licensed, rigged full-body GLB to preview an animated character. Your selected photo remains a private reference preview only.</span></div>}
        <div className="tp-stage-label"><i/> CLASSROOM · {model ? "LOCAL RIGGED GLB" : "NO HUMAN AVATAR"}</div>
        <div className="tp-stage-actions"><button onClick={() => setCinematic(value => !value)} aria-pressed={cinematic}>Camera: {cinematic ? "Cinematic" : "Wide"}</button><button onClick={() => void fullscreenToggle()}>{fullscreen ? "Exit fullscreen" : "Fullscreen"}</button></div>
        <div className="tp-stage-caption" aria-live="polite">{model ? `${expression} · ${state}` : "AI tutoring and lesson board are available below."}</div>
      </section>
      <aside className="tp-panel" aria-label="Teacher controls">
        <div className="tp-panel-heading"><span className="tp-kicker">TEACHER STUDIO</span><h2>Direct the lesson</h2></div>
        <div className="tp-board" aria-label="Interactive lesson board"><span className="tp-label">LESSON BOARD · SESSION CONTENT</span><h3>{lesson.title}</h3><p>{lesson.detail}</p>{boardReply && <article>{boardReply.content}</article>}{boardQuestion && <small>Latest student question: {boardQuestion.content}</small>}</div>
        {sessionId ? <Link className="tp-open-tutor" to={`/voice?session=${encodeURIComponent(sessionId)}`}>Open live AI tutor and microphone ↗</Link> : <Link className="tp-open-tutor" to="/dashboard">Choose a lesson from your dashboard ↗</Link>}
        <section className="tp-lesson-context" aria-label="Shared lesson context">
          <span className="tp-label">SHARED LESSON</span>
          <strong>{lesson.title}</strong>
          <p>{lesson.detail}</p>
          {lessonContext && <small>{lesson.language} · {lesson.level}</small>}
          {!lessonContext && <small role={contextError ? "alert" : "status"}>{contextError || (sessionId ? "Loading shared session…" : "Connect a session to load its lesson context.")}</small>}
        </section>
        <div className="tp-control-grid">{controls}</div>
        <div className="tp-control-block"><span className="tp-label">MOVEMENT</span>{model ? <div className="tp-buttons"><button onClick={() => runAction({ type: "walkTo", x: 0, z: -0.5 })}>Walk</button><button onClick={() => runAction({ type: "lookAt", x: 0, y: 2, z: -5 })}>Turn to board</button><button onClick={() => runAction({ type: "explain", durationMs: 2600 })}>Explain</button></div> : <small role="note">Walking, turning, gestures, and pointing are unavailable until a compatible rigged GLB is loaded.</small>}</div>
        {model && <div className="tp-control-block"><span className="tp-label">SMARTBOARD POINTING</span><label className="tp-control">Board position<select onChange={event => { const [x, y] = event.target.value.split(",").map(Number); runAction({ type: "pointAt", target: { x, y } }); }} defaultValue="0.72,0.34"><option value="0.72,0.34">Upper right · (0.72, 0.34)</option><option value="0.28,0.58">Center left · (0.28, 0.58)</option><option value="0.5,0.5">Center · (0.5, 0.5)</option></select></label></div>}
        <section className="tp-control-block tp-upload tp-photo-upload" aria-label="Photo teacher">
          <span className="tp-label">PHOTO-BASED HUMAN TEACHER</span>
          <label className="tp-photo-consent"><input type="checkbox" checked={photoPermission} onChange={event => { setPhotoPermission(event.target.checked); if (!event.target.checked) removePhoto(); }} /> I have permission to use this person's likeness.</label>
          <label className="tp-upload-button">{photoAsset ? "Change photo" : "Choose full-body photo"}<input type="file" accept="image/png,image/jpeg,image/webp" aria-label="Choose full-body teacher photo" disabled={!photoPermission || photoBusy} onChange={loadPhoto} /></label>
          {photoBusy && <small role="status">Checking and previewing photo…</small>}
          {photoAsset && <div className="tp-photo-preview"><img src={photoAsset.previewUrl} alt={`Selected teacher photo: ${photoAsset.name}`} /><div><strong>{photoAsset.name}</strong><small>{photoAsset.width} x {photoAsset.height} · stays in this browser</small><button type="button" onClick={removePhoto}>Remove photo</button></div></div>}
          {photoError && <p className="tp-photo-error" role="alert">{photoError}</p>}
          <small>Photo stays in this browser and is never sent to Gemini or Gnani. It is shown only in the preview below; one photo cannot create a realistic rigged 3D teacher.</small>
        </section>
        <div className="tp-control-block tp-upload"><span className="tp-label">LOCAL AVATAR ASSET</span><label className="tp-upload-button">Choose GLB<input type="file" accept=".glb,model/gltf-binary" onChange={loadLocalModel}/></label><small>{modelStatus}</small><small>Use an asset you have rights to use. Nothing is downloaded remotely.</small></div>
        <label className="tp-motion-toggle"><input type="checkbox" checked={reduced} onChange={event => setReduced(event.target.checked)}/> Reduce motion</label>
      </aside>
    </section>
    <footer className="tp-footer"><span>AI responses and voice are separate from the optional local avatar.</span><span>WebGL · local licensed assets only · no photo upload to providers</span></footer>
  </main>;
}
