import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import { getSharedSessionContext } from "./sessionContext";
import { DEFAULT_LEARNING_PREFERENCES, mergeLearningPreferences, type LearningPreferences } from "./learningPreferences";
import { SessionModeNav } from "./SessionModeNav";
import { PracticeAssessment } from "./PracticeAssessment";
import { AvatarSyncController, type SyncMode } from "./avatarSync";
import { immersiveVoiceBridge } from "./immersiveVoiceBridge";
import { matchVoiceNavigationCommand } from "./voiceNavigation.mjs";
import { DesktopControlPanel } from "./DesktopControlPanel";
import { wavFromFloatChunks } from "./voiceWav";
import { measureVoiceAudio, type VoiceAudioMetrics } from "./voiceAudioMetrics";
import "./voice.css";

type Language = "english" | "telugu" | "mixed";
type Session = { id: string; topic: string; language: Language; created_at: string };
type Message = { id: string; role: "user" | "assistant"; content: string; created_at: string; language?: Language };
type TutorReply = { reply: string; session_id: string; language: string; learning_level: string };
type PrismaDiagnostics = {
  provider_status: "success"; provider_latency_ms: number; provider_model: string;
  provider_language_code: string; provider_format: string;
  audio_sample_rate_hz: number; audio_channels: number; audio_bits_per_sample: number;
};
type Preferences = LearningPreferences;
type PlaybackState = "idle" | "listening" | "thinking" | "speaking" | "paused" | "interrupted" | "error";
type ResumeStatus = "none" | "awaiting_confirmation" | "resumed" | "dismissed";
type VoiceLessonState = {
  session_id: string; topic: string; lesson_step: string; student_question: string | null;
  active_response_language: Language; playback_state: PlaybackState; voice_transcript: string | null;
  checkpoint_message_id: string | null; checkpoint_playback_ms: number | null;
  resume_status: ResumeStatus; updated_at?: string | null;
};
const headers = () => ({ Authorization: "Bearer " + getToken() });
function errorText(cause: unknown) { return cause instanceof Error ? cause.message : "Something went wrong."; }
function optimisticPlaceholder(content: string): Message { return { id: "local-demo-user-" + Date.now(), role: "user", content, created_at: new Date().toISOString() }; }

function localDemoWav(): Blob {
  const sampleRate = 16000;
  const samples = sampleRate * 2;
  const bytes = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(bytes);
  const write = (offset: number, value: string) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  write(0, "RIFF"); view.setUint32(4, bytes.byteLength - 8, true); write(8, "WAVE");
  write(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, "data"); view.setUint32(40, samples * 2, true);
  for (let index = 0; index < samples; index += 1) {
    const time = index / sampleRate;
    const syllable = Math.sin(Math.PI * Math.min(1, (time % 0.42) / 0.42));
    const sample = Math.sin(2 * Math.PI * 220 * time) * syllable * 0.12;
    view.setInt16(44 + index * 2, Math.round(sample * 0x7fff), true);
  }
  return new Blob([bytes], { type: "audio/wav" });
}

async function readAudioResponse(response: Response): Promise<Blob> {
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = body?.detail;
    throw new ApiError(response.status, typeof detail === "string" ? detail : "Speech generation failed. You can still read the tutor response.");
  }
  if (!response.headers.get("content-type")?.toLowerCase().startsWith("audio/wav")) throw new Error("The speech service returned an unsupported audio format.");
  const blob = await response.blob();
  if (!blob.size) throw new Error("The speech service returned empty audio.");
  return blob;
}

export function VoiceTutor({ immersive = false, forceDemo = false, onClose }: { immersive?: boolean; forceDemo?: boolean; onClose?: () => void } = {}) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [student, setStudent] = useState<Student | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState("");
  const [language, setLanguage] = useState<Language>("mixed");
  const [preferences, setPreferences] = useState<Preferences>(DEFAULT_LEARNING_PREFERENCES);
  const [topic, setTopic] = useState("");
  const [draft, setDraft] = useState("");
  const pendingNavigation = matchVoiceNavigationCommand(draft);
  const [messages, setMessages] = useState<Message[]>([]);
  const [recording, setRecording] = useState(false);
  const [micStarting, setMicStarting] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [syncMode, setSyncMode] = useState<SyncMode>("silent");
  const syncModeRef = useRef<SyncMode>("silent");
  const [mouthViseme, setMouthViseme] = useState("sil");
  const [playbackRun, setPlaybackRun] = useState(0);
  const [speechLoading, setSpeechLoading] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [captureMetrics, setCaptureMetrics] = useState<VoiceAudioMetrics | null>(null);
  const [prismaDiagnostics, setPrismaDiagnostics] = useState<PrismaDiagnostics | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [playbackElementKey, setPlaybackElementKey] = useState(0);
  const [demoMode, setDemoMode] = useState(false);
  const [localDemoAvailable, setLocalDemoAvailable] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [replyLatencyMs, setReplyLatencyMs] = useState<number | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceLessonState | null>(null);
  const [resumePrompt, setResumePrompt] = useState(false);
  const [providerConfigured, setProviderConfigured] = useState<boolean | null>(null);
  const [mobileMenu, setMobileMenu] = useState(false);
  const scrollBottom = useRef<HTMLDivElement>(null);
  const activeHistory = useRef(0);
  const selectedRef = useRef("");
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const muteRef = useRef<GainNode | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
  const audioCache = useRef(new Map<string, string>());
  const audioRef = useRef<HTMLAudioElement>(null);
  const pendingPlaybackOffsetRef = useRef(0);
  const interruptingRef = useRef(false);
  const voiceStateRef = useRef<VoiceLessonState | null>(null);
  const voiceStateWriteRef = useRef<Promise<void>>(Promise.resolve());
  const syncGenerationRef = useRef<number | null>(null);
  const audioLanguageRef = useRef<Language>("mixed");
  const mouthVisemeRef = useRef("sil");
  const playbackContextRef = useRef<AudioContext | null>(null);
  const playbackAnalyserRef = useRef<AnalyserNode | null>(null);
  const playbackSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const playbackSamplesRef = useRef<Uint8Array<ArrayBuffer> | null>(null);
  const syncControllerRef = useRef<AvatarSyncController | null>(null);
  if (!syncControllerRef.current) syncControllerRef.current = new AvatarSyncController(frame => {
    immersiveVoiceBridge.acceptFrame(frame);
    if (!mounted.current) return;
    if (syncModeRef.current !== frame.mode) { syncModeRef.current = frame.mode; setSyncMode(frame.mode); }
    if (mouthVisemeRef.current !== frame.viseme) { mouthVisemeRef.current = frame.viseme; setMouthViseme(frame.viseme); }
  });
  const speechRequestRef = useRef<AbortController | null>(null);
  const transcriptionRequestRef = useRef<AbortController | null>(null);
  const recordingActive = useRef(false);
  const micRequestActive = useRef(false);
  const voiceTurnActive = useRef(false);
  const recordingTimer = useRef<number | null>(null);
  const speechStartedAtRef = useRef<number | null>(null);
  const lastSpeechAtRef = useRef<number>(0);
  const mounted = useRef(true);

  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);
  const handleError = useCallback((cause: unknown) => {
    if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
    setError(errorText(cause));
  }, [signOut]);

  const releaseMicrophone = useCallback(async () => {
    if (processorRef.current) { processorRef.current.onaudioprocess = null; processorRef.current.disconnect(); processorRef.current = null; }
    sourceRef.current?.disconnect(); sourceRef.current = null;
    muteRef.current?.disconnect(); muteRef.current = null;
    streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null;
    const context = contextRef.current; contextRef.current = null;
    if (context && context.state !== "closed") await context.close().catch(() => undefined);
  }, []);

  useEffect(() => {
    let active = true;
    const enableLocalDemo = () => {
      setDemoMode(true); setStudent({ id: "local-demo", email: "demo@local.invalid", display_name: "Local demo learner" });
      setSessions([{ id: "local-demo-session", topic: "Voice synchronization demo", language: "mixed", created_at: new Date().toISOString() }]);
      setSelected("local-demo-session"); setLanguage("mixed");
      setMessages([{ id: "local-demo-reply", role: "assistant", content: "Local demo mode is active. This short generated tone demonstrates avatar timing only; it is not Gnani speech.", created_at: new Date().toISOString() }]);
      setNotice("Backend unavailable. Local demo mode uses a generated tone and does not record or send microphone audio.");
    };
    const token = getToken();
    if (!token) { signOut(); return; }
    if (forceDemo) { enableLocalDemo(); setLoading(false); return () => { active = false; }; }
    request<{ configured: boolean }>("/voice/sessions/provider-mode", { headers: { Authorization: "Bearer " + token } })
      .then(status => { if (active) setProviderConfigured(status.configured); })
      .catch(() => { if (active) setProviderConfigured(false); });
    Promise.all([
      getCurrentStudent(token),
      request<Session[]>("/sessions?limit=100", { headers: { Authorization: "Bearer " + token } }),
      request<Preferences>("/students/me/preferences", { headers: { Authorization: "Bearer " + token } }),
    ]).then(([profile, list, prefs]) => {
      if (!active) return;
      setStudent(profile); setSessions(list); setPreferences(prefs); setLanguage(prefs.preferred_language);
      const requested = params.get("session");
      if (requested && list.some(item => item.id === requested)) setSelected(requested);
      else if (!requested && list.length) setSelected(list[0].id);
      else if (requested) setError("That learning session is unavailable. Choose one of your sessions or return to your dashboard.");
    }).catch(cause => {
      if (!active) return;
      if (cause instanceof ApiError && cause.status === 401) { handleError(cause); return; }
      if (immersive && (cause instanceof ApiError && (cause.status === 0 || cause.status >= 500))) enableLocalDemo();
      else handleError(cause);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [forceDemo, handleError, immersive, signOut]);

  useEffect(() => {
    selectedRef.current = selected;
    const loadId = ++activeHistory.current;
    voiceStateRef.current = null;
    setVoiceState(null);
    setResumePrompt(false);
    if (demoMode || forceDemo) { setHistoryLoading(false); return; }
    setMessages([]);
    if (!selected) { setHistoryLoading(false); return; }
    setHistoryLoading(true);
    Promise.all([
      getSharedSessionContext(selected),
      request<VoiceLessonState>(`/voice/sessions/${encodeURIComponent(selected)}/state`, { headers: headers() }).catch(() => null),
    ])
      .then(([context, state]) => {
        if (loadId !== activeHistory.current) return;
        setMessages(context.messages);
        setLanguage(state?.active_response_language || context.preferred_language);
        setPreferences({ preferred_language: context.preferred_language, learning_level: context.learning_level, learning_pace: context.learning_pace, learning_goal: context.learning_goal });
        voiceStateRef.current = state;
        setVoiceState(state);
        setResumePrompt(state?.resume_status === "awaiting_confirmation" && Boolean(state.checkpoint_message_id));
      })
      .catch(cause => { if (loadId === activeHistory.current) handleError(cause); })
      .finally(() => { if (loadId === activeHistory.current) setHistoryLoading(false); });
  }, [selected, demoMode, forceDemo, handleError]);

  useEffect(() => { scrollBottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, busy]);
  useEffect(() => {
    if (!audioUrl || !audioRef.current) return;
    if (pendingPlaybackOffsetRef.current > 0) {
      audioRef.current.currentTime = pendingPlaybackOffsetRef.current;
      pendingPlaybackOffsetRef.current = 0;
    }
    const generation = syncControllerRef.current!.begin({}, audioLanguageRef.current);
    syncGenerationRef.current = generation;
    void audioRef.current.play().catch(() => {
      if (!mounted.current || syncGenerationRef.current !== generation) return;
      setNotice("Audio is ready. Press Play to start playback."); immersiveVoiceBridge.setState("error");
    });
  }, [audioUrl, playbackElementKey]);
  useEffect(() => {
    if (!speaking) return;
    const audio = audioRef.current;
    const generation = syncGenerationRef.current;
    if (!audio || generation === null) return;
    let animationFrame = 0;
    const animate = () => {
      let level: number | undefined;
      const analyser = playbackAnalyserRef.current;
      const samples = playbackSamplesRef.current;
      if (analyser && samples) {
        analyser.getByteTimeDomainData(samples);
        let energy = 0;
        for (const sample of samples) { const normalized = (sample - 128) / 128; energy += normalized * normalized; }
        level = Math.sqrt(energy / samples.length);
      }
      syncControllerRef.current?.tick(generation, { currentTime: audio.currentTime, duration: audio.duration, paused: audio.paused, ended: audio.ended }, level);
      if (!audio.paused && !audio.ended) animationFrame = window.requestAnimationFrame(animate);
    };
    animationFrame = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(animationFrame);
  }, [speaking, playbackRun]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (recordingTimer.current !== null) window.clearInterval(recordingTimer.current);
      void releaseMicrophone();
      speechRequestRef.current?.abort(); speechRequestRef.current = null;
      transcriptionRequestRef.current?.abort(); transcriptionRequestRef.current = null;
      syncControllerRef.current?.cancel();
      syncGenerationRef.current = null;
      audioRef.current?.pause();
      if (audioRef.current) audioRef.current.currentTime = 0;
      if (playbackSourceRef.current) { playbackSourceRef.current.disconnect(); playbackSourceRef.current = null; }
      if (playbackContextRef.current && playbackContextRef.current.state !== "closed") void playbackContextRef.current.close();
      audioCache.current.forEach(url => URL.revokeObjectURL(url));
      immersiveVoiceBridge.clear();
    };
  }, [releaseMicrophone]);

  async function saveVoiceState(patch: Partial<VoiceLessonState>, sessionId = selected) {
    if (!sessionId) return;
    const write = voiceStateWriteRef.current.catch(() => undefined).then(async () => {
      const previous = voiceStateRef.current?.session_id === sessionId ? voiceStateRef.current : null;
      const next = {
        lesson_step: previous?.lesson_step || "introduction",
        student_question: previous?.student_question ?? null,
        active_response_language: previous?.active_response_language || language,
        playback_state: previous?.playback_state || "idle",
        voice_transcript: previous?.voice_transcript ?? null,
        checkpoint_message_id: previous?.checkpoint_message_id ?? null,
        checkpoint_playback_ms: previous?.checkpoint_playback_ms ?? null,
        resume_status: previous?.resume_status || "none",
        ...patch,
      };
      try {
        const updated = await request<VoiceLessonState>(`/voice/sessions/${encodeURIComponent(sessionId)}/state`, {
          method: "PUT", headers: headers(), body: JSON.stringify(next),
        });
        if (selectedRef.current === sessionId) {
          voiceStateRef.current = updated;
          setVoiceState(updated);
        }
      } catch (cause) {
        if (selectedRef.current === sessionId) {
          if (cause instanceof ApiError && cause.status === 401) handleError(cause);
          else setNotice("Voice checkpoint could not be saved: " + errorText(cause));
        }
      }
    });
    voiceStateWriteRef.current = write;
    await write;
  }

  function stopPlayback(preservePosition = false) {
    speechRequestRef.current?.abort(); speechRequestRef.current = null;
    const wasActive = syncGenerationRef.current !== null || speaking || speechLoading;
    if (syncGenerationRef.current !== null) syncControllerRef.current?.cancel(syncGenerationRef.current);
    syncGenerationRef.current = null;
    if (wasActive) immersiveVoiceBridge.setState("interrupted");
    if (audioRef.current) { audioRef.current.pause(); if (!preservePosition) audioRef.current.currentTime = 0; }
    setSpeaking(false); setSpeechLoading(false);
  }

  function interruptSpeechForQuestion() {
    if (!speaking && !speechLoading) return;
    const latestAssistant = [...messages].reverse().find(message => message.role === "assistant");
    const checkpoint = {
      checkpoint_message_id: latestAssistant?.id || null,
      checkpoint_playback_ms: Math.max(0, Math.round((audioRef.current?.currentTime || 0) * 1000)),
      student_question: null,
      active_response_language: language,
      playback_state: "interrupted" as const,
      resume_status: latestAssistant ? "awaiting_confirmation" as const : "none" as const,
    };
    setResumePrompt(Boolean(latestAssistant));
    void saveVoiceState(checkpoint);
    interruptingRef.current = true;
    immersiveVoiceBridge.setState("interrupted");
    stopPlayback(true);
    window.setTimeout(() => {
      if (interruptingRef.current && (!audioRef.current || audioRef.current.paused)) interruptingRef.current = false;
    }, 1000);
  }
  function startPlaybackSync(elementKey = playbackElementKey) {
    if (!mounted.current || elementKey !== playbackElementKey) return;
    const controller = syncControllerRef.current!;
    if (syncGenerationRef.current === null || ["completed", "interrupted", "error"].includes(controller.currentState())) {
      syncGenerationRef.current = controller.begin({}, audioLanguageRef.current);
    }
    controller.play(syncGenerationRef.current);
    const audio = audioRef.current;
    if (audio && !playbackAnalyserRef.current && typeof AudioContext !== "undefined") {
      try {
        const context = new AudioContext();
        const analyser = context.createAnalyser(); analyser.fftSize = 256;
        const source = context.createMediaElementSource(audio);
        source.connect(analyser); analyser.connect(context.destination);
        void context.resume().catch(() => undefined);
        playbackContextRef.current = context; playbackAnalyserRef.current = analyser;
        playbackSourceRef.current = source; playbackSamplesRef.current = new Uint8Array(new ArrayBuffer(analyser.fftSize));
      } catch { /* Playback continues; the controller labels its timing-based mouth motion as approximate. */ }
    }
    setSpeaking(true); setPlaybackRun(value => value + 1);
    immersiveVoiceBridge.setState("speaking");
    if (!demoMode) void saveVoiceState({ playback_state: "speaking" });
  }
  function pausePlaybackSync(elementKey = playbackElementKey) {
    if (interruptingRef.current) { interruptingRef.current = false; setSpeaking(false); return; }
    if (!mounted.current || elementKey !== playbackElementKey || !audioRef.current || audioRef.current.ended || syncGenerationRef.current === null) return;
    syncControllerRef.current?.pause(syncGenerationRef.current);
    setSpeaking(false);
    immersiveVoiceBridge.setState("paused");
    if (!demoMode) void saveVoiceState({ playback_state: "paused" });
  }
  function completePlaybackSync(elementKey = playbackElementKey) {
    if (!mounted.current || elementKey !== playbackElementKey) return;
    if (syncGenerationRef.current !== null) syncControllerRef.current?.complete(syncGenerationRef.current);
    else immersiveVoiceBridge.setState("idle");
    setSpeaking(false);
    if (!demoMode) void saveVoiceState({ playback_state: "idle" });
  }
  function chooseSession(id: string) {
    if (busy || transcribing || recording) return;
    stopPlayback();
    setError(""); setNotice(""); setAudioUrl(""); setSelected(id); setParams({ session: id }); setMobileMenu(false);
  }

  async function createSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!topic.trim() || creating) return;
    setCreating(true); setError("");
    try {
      const session = await request<Session>("/sessions", { method: "POST", headers: headers(), body: JSON.stringify({ topic: topic.trim(), language }) });
      setSessions(list => [session, ...list]); setTopic(""); setSelected(session.id); setParams({ session: session.id });
    } catch (cause) { handleError(cause); } finally { setCreating(false); }
  }

  async function changeLanguage(value: Language) {
    if (busy || recording || transcribing) return;
    const previous = language; setLanguage(value); setError(""); setNotice("");
    if (demoMode) { setPreferences(current => mergeLearningPreferences(current, { preferred_language: value })); setNotice("Local demo language updated; mouth motion remains approximate."); return; }
    try {
      const updated = await request<Preferences>("/students/me/preferences", { method: "PUT", headers: headers(), body: JSON.stringify(mergeLearningPreferences(preferences, { preferred_language: value })) });
      setPreferences(updated); setNotice("Tutor language updated. Your session and conversation remain unchanged.");
      if (!demoMode) void saveVoiceState({ active_response_language: value });
    } catch (cause) { setLanguage(previous); handleError(cause); }
  }

  async function transcribeWav(blob: Blob) {
    const sessionId = selected;
    if (!sessionId) return;
    transcriptionRequestRef.current?.abort();
    const controller = new AbortController();
    transcriptionRequestRef.current = controller;
    setTranscribing(true); setError(""); setPrismaDiagnostics(null); setNotice(`Sending ${blob.size.toLocaleString()} byte PCM WAV to Gnani Prisma…`);
    try {
      const form = new FormData(); form.append("audio", blob, "microphone.wav"); form.append("language", language);
      const response = await fetch(`/api/v1/voice/sessions/${encodeURIComponent(sessionId)}/transcribe`, { method: "POST", headers: { ...headers(), "X-Request-ID": crypto.randomUUID() }, body: form, signal: controller.signal });
      const body = await response.json().catch(() => null) as ({ transcript?: unknown; detail?: unknown } & Partial<PrismaDiagnostics>) | null;
      if (!response.ok) throw new ApiError(response.status, typeof body?.detail === "string" ? body.detail : "Speech transcription failed. You can type your question instead.");
      if (selectedRef.current !== sessionId) return;
      if (body?.provider_status === "success" && typeof body.provider_latency_ms === "number" && Number.isFinite(body.provider_latency_ms) && typeof body.provider_model === "string" && typeof body.provider_language_code === "string" && typeof body.provider_format === "string" && typeof body.audio_sample_rate_hz === "number" && typeof body.audio_channels === "number" && typeof body.audio_bits_per_sample === "number") {
        setPrismaDiagnostics({
          provider_status: body.provider_status, provider_latency_ms: body.provider_latency_ms,
          provider_model: body.provider_model, provider_language_code: body.provider_language_code,
          provider_format: body.provider_format, audio_sample_rate_hz: body.audio_sample_rate_hz,
          audio_channels: body.audio_channels, audio_bits_per_sample: body.audio_bits_per_sample,
        });
      }
      if (typeof body?.transcript !== "string" || !body.transcript.trim()) throw new Error("Prisma did not recognize speech. Try again or type your question.");
      setDraft(body.transcript); setNotice("Transcript ready. Review or correct it, then send it to your tutor.");
      if (!demoMode) void saveVoiceState({ voice_transcript: body.transcript, playback_state: resumePrompt ? "interrupted" : "idle" }, sessionId);
    } catch (cause) { if (!controller.signal.aborted) handleError(cause); }
    finally { if (transcriptionRequestRef.current === controller) transcriptionRequestRef.current = null; setTranscribing(false); }
  }

  async function finishRecording() {
    if (!recordingActive.current) return;
    immersiveVoiceBridge.setState("thinking");
    voiceTurnActive.current = true;
    recordingActive.current = false; setRecording(false); setRecordingSeconds(0);
    setTranscribing(true);
    if (recordingTimer.current !== null) { window.clearInterval(recordingTimer.current); recordingTimer.current = null; }
    const context = contextRef.current;
    try {
      try { if (context) setCaptureMetrics(measureVoiceAudio(chunksRef.current, context.sampleRate)); }
      finally { await releaseMicrophone(); }
      await transcribeWav(wavFromFloatChunks(chunksRef.current, context?.sampleRate || 48000));
    }
    catch (cause) { handleError(cause); }
    finally { setTranscribing(false); chunksRef.current = []; voiceTurnActive.current = false; if (immersiveVoiceBridge.getState() === "thinking") immersiveVoiceBridge.setState("idle"); }
  }

  async function toggleRecording() {
    if (recordingActive.current) { await finishRecording(); return; }
    setError(""); setNotice(""); interruptSpeechForQuestion();
    if (demoMode) { setError("Microphone capture is unavailable in local demo mode. Type a question to continue."); immersiveVoiceBridge.setState("error"); return; }
    if (!selected || busy || transcribing || voiceTurnActive.current || micRequestActive.current) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioContext === "undefined") { setError("Microphone recording is unavailable in this browser. Type your question instead."); immersiveVoiceBridge.setState("error"); return; }
    immersiveVoiceBridge.setState("listening");
    micRequestActive.current = true; voiceTurnActive.current = true; setMicStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (!mounted.current) { stream.getTracks().forEach(track => track.stop()); return; }
      streamRef.current = stream;
      const context = new AudioContext();
      contextRef.current = context;
      await context.resume();
      const source = context.createMediaStreamSource(stream);
      sourceRef.current = source;
      const processor = context.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      const mute = context.createGain(); mute.gain.value = 0;
      muteRef.current = mute;
      chunksRef.current = [];
      speechStartedAtRef.current = null; lastSpeechAtRef.current = 0;
      processor.onaudioprocess = event => {
        const samples = new Float32Array(event.inputBuffer.getChannelData(0));
        chunksRef.current.push(samples);
        let energy = 0;
        for (const sample of samples) energy += sample * sample;
        const rms = Math.sqrt(energy / Math.max(1, samples.length));
        const now = performance.now();
        // Stop shortly after the utterance instead of sending up to 30 seconds of room noise.
        // Low-gain Windows microphones can deliver speech below -40 dBFS even with AGC.
        if (rms >= 0.0045) {
          speechStartedAtRef.current ??= now;
          lastSpeechAtRef.current = now;
        } else if (speechStartedAtRef.current !== null && now - lastSpeechAtRef.current >= 1400) {
          void finishRecording();
        }
      };
      source.connect(processor); processor.connect(mute); mute.connect(context.destination);
      recordingActive.current = true; setRecording(true);
      if (!demoMode) void saveVoiceState({ playback_state: "listening" });
      const started = Date.now();
      const timer = window.setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000); setRecordingSeconds(elapsed);
        if (elapsed >= 30) void finishRecording();
      }, 500);
      recordingTimer.current = timer;
    } catch {
      await releaseMicrophone(); recordingActive.current = false; voiceTurnActive.current = false; setRecording(false);
      setError("Microphone access was denied or could not start. Typed chat remains available.");
      immersiveVoiceBridge.setState("error");
    } finally { micRequestActive.current = false; if (mounted.current) setMicStarting(false); }
  }

  function generateLocalDemo(text: string, sessionId: string, mode: Language) {
    const cacheKey = `${sessionId}:${mode}:local-demo:${text}`;
    let url = audioCache.current.get(cacheKey);
    if (!url) { url = URL.createObjectURL(localDemoWav()); audioCache.current.set(cacheKey, url); }
    audioLanguageRef.current = mode; setError(""); setLocalDemoAvailable(false); stopPlayback();
    if (audioUrl === url) setPlaybackElementKey(value => value + 1);
    else setAudioUrl(url);
    setNotice("Playing a local demo tone for avatar timing; this is not generated speech.");
  }

  async function generateSpeech(text: string, sessionId: string, mode: Language, offsetMs = 0) {
    audioLanguageRef.current = mode;
    const cacheKey = `${sessionId}:${mode}:${text}`;
    const cached = audioCache.current.get(cacheKey);
    if (demoMode) { generateLocalDemo(text, sessionId, mode); return; }
    if (cached) {
      if (audioUrl === cached && audioRef.current) {
        audioRef.current.currentTime = Math.max(0, offsetMs) / 1000;
        void audioRef.current.play().catch(() => setNotice("Audio is ready. Press Play to start playback."));
      } else { stopPlayback(); pendingPlaybackOffsetRef.current = Math.max(0, offsetMs) / 1000; setAudioUrl(cached); }
      return;
    }
    stopPlayback(); setAudioUrl("");
    immersiveVoiceBridge.setState("thinking");
    setSpeechLoading(true);
    const controller = new AbortController(); speechRequestRef.current = controller;
    try {
      const response = await fetch(`/api/v1/voice/sessions/${encodeURIComponent(sessionId)}/speech`, {
        method: "POST", headers: { ...headers(), "Content-Type": "application/json" }, body: JSON.stringify({ text, language: mode }), signal: controller.signal,
      });
      const blob = await readAudioResponse(response);
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob); audioCache.current.set(cacheKey, url); pendingPlaybackOffsetRef.current = Math.max(0, offsetMs) / 1000; setAudioUrl(url); setNotice("Timbre audio is ready.");
      if (audioCache.current.size > 20) {
        const oldest = audioCache.current.keys().next().value;
        if (oldest) { URL.revokeObjectURL(audioCache.current.get(oldest)!); audioCache.current.delete(oldest); }
      }
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ApiError && cause.status === 401) { handleError(cause); return; }
      setNotice("Tutor response is saved as text. Speech playback failed: " + errorText(cause));
      immersiveVoiceBridge.setState("error"); setLocalDemoAvailable(true);
    }
    finally { if (speechRequestRef.current === controller) { speechRequestRef.current = null; if (mounted.current) setSpeechLoading(false); } }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || !selected || busy || transcribing || recording || historyLoading) return;
    const sessionId = selected;
    const checkpoint = voiceStateRef.current?.session_id === sessionId
      && Boolean(voiceStateRef.current.checkpoint_message_id)
      && voiceStateRef.current.resume_status === "awaiting_confirmation";
    setBusy(true); setError(""); setNotice(""); setDraft(""); stopPlayback(); immersiveVoiceBridge.setState("thinking");
    if (demoMode) {
      const localReply: Message = { id: "local-demo-reply-" + Date.now(), role: "assistant", content: "I heard your typed question in this local demo. The response is example text and no backend was contacted.", created_at: new Date().toISOString() };
      setMessages(items => [...items, optimisticPlaceholder(message), localReply]);
      setBusy(false); immersiveVoiceBridge.setState("idle");
      if (autoSpeak) generateLocalDemo(localReply.content, sessionId, language);
      return;
    }
    void saveVoiceState({ student_question: message, voice_transcript: message, active_response_language: language, playback_state: "thinking" }, sessionId);
    const optimistic: Message = { id: "pending-" + Date.now(), role: "user", content: message, created_at: new Date().toISOString() };
    setMessages(items => [...items, optimistic]);
    const requestStartedAt = performance.now();
    try {
      const result = await request<TutorReply>(`/tutor/sessions/${encodeURIComponent(sessionId)}/chat`, { method: "POST", headers: headers(), body: JSON.stringify({ message, language }) });
      setReplyLatencyMs(Math.round(performance.now() - requestStartedAt));
      if (selectedRef.current === sessionId) setMessages(items => [...items, { id: "reply-" + Date.now(), role: "assistant", content: result.reply, created_at: new Date().toISOString(), language: result.language as Language }]);
      if (autoSpeak && selectedRef.current === sessionId) await generateSpeech(result.reply, sessionId, result.language as Language);
      if (selectedRef.current === sessionId && !demoMode) {
        void saveVoiceState({
          student_question: checkpoint ? message : null,
          voice_transcript: message,
          active_response_language: language,
          playback_state: autoSpeak ? "speaking" : "idle",
          resume_status: checkpoint ? "awaiting_confirmation" : "none",
        }, sessionId);
        if (checkpoint) setResumePrompt(true);
      }
    } catch (cause) {
      setMessages(items => items.filter(item => item.id !== optimistic.id)); setDraft(message); handleError(cause);
    } finally { setBusy(false); if (!speaking && immersiveVoiceBridge.getState() === "thinking") immersiveVoiceBridge.setState("idle"); }
  }

  async function resumeCheckpoint() {
    const checkpoint = voiceStateRef.current;
    if (!checkpoint?.checkpoint_message_id) return;
    const message = messages.find(item => item.id === checkpoint.checkpoint_message_id && item.role === "assistant");
    if (!message) {
      setResumePrompt(false);
      await saveVoiceState({ resume_status: "dismissed", playback_state: "idle" }, checkpoint.session_id);
      setNotice("The saved lesson audio is no longer available. Choose a tutor reply to continue.");
      return;
    }
    setResumePrompt(false);
    await saveVoiceState({ resume_status: "resumed", playback_state: "speaking", student_question: null }, checkpoint.session_id);
    await generateSpeech(message.content, checkpoint.session_id, checkpoint.active_response_language, checkpoint.checkpoint_playback_ms || 0);
  }

  async function dismissResume() {
    setResumePrompt(false);
    await saveVoiceState({ resume_status: "dismissed", playback_state: "idle", student_question: null });
  }

  const current = sessions.find(session => session.id === selected);
  const MainElement = immersive ? "section" : "main";
  if (loading) return <main className="auth-screen"><p className="auth-wait">Opening your voice studio…</p></main>;
  if (!student) return <main className="auth-screen"><div className="cl-fatal"><h2>Voice studio unavailable</h2><p role="alert">{error}</p><button onClick={() => window.location.reload()}>Retry</button><button onClick={signOut}>Sign out</button></div></main>;
  return <div className={immersive ? `vt-app vt-app-immersive${sessions.length ? "" : " vt-no-sessions"}` : "vt-app"}>
    <aside className={mobileMenu ? "vt-sidebar vt-sidebar-open" : "vt-sidebar"}>
      <Link className="vt-brand" to="/dashboard"><span>✦</span> BHASHA<strong>LEARN</strong> AI</Link>
      <Link to="/dashboard" className="vt-back">← Student dashboard</Link>
      <div className="vt-side-label">YOUR VOICE SESSIONS</div>
      <nav className="vt-sessions" aria-label="Voice learning sessions">{sessions.map(session => <button key={session.id} className={session.id === selected ? "vt-session-active" : ""} disabled={busy || transcribing || recording} onClick={() => chooseSession(session.id)}><span>◉</span><span><strong>{session.topic}</strong><small>{session.language} · {new Date(session.created_at).toLocaleDateString()}</small></span></button>)}{!sessions.length && <p>Start your first session to begin.</p>}</nav>
      <div className="vt-side-profile"><span>{student.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{student.display_name}</strong><small>Voice learner</small></div></div>
    </aside>
    <MainElement className="vt-main" aria-label={immersive ? "Voice tutor controls" : undefined}>
      <header className="vt-topbar"><div><button className="vt-mobile-menu" onClick={() => setMobileMenu(!mobileMenu)} aria-label="Toggle sessions">☰</button><span className="vt-eyebrow">✦ VOICE LEARNING STUDIO</span>{demoMode && <span className="vt-demo-badge">LOCAL DEMO - NO GNANI AUDIO</span>}<h2>{current?.topic || "Your voice classroom"}</h2></div><div className="vt-top-actions">{immersive && <label>Learning session <select aria-label="Voice learning session" value={selected} disabled={busy || transcribing || recording} onChange={event => chooseSession(event.target.value)}>{sessions.map(item => <option key={item.id} value={item.id}>{item.topic}</option>)}</select></label>}<label>Tutor language <select value={language} disabled={recording || transcribing || busy} onChange={event => void changeLanguage(event.target.value as Language)}><option value="mixed">Telugu + English</option><option value="english">English</option><option value="telugu">తెలుగు</option></select></label></div>{!immersive && <SessionModeNav sessionId={selected} active="voice"/>}{onClose && <button type="button" className="vt-embedded-close" onClick={onClose} aria-label="Close voice tutor">Close</button>}</header>
      <div className="vt-layout"><section className="vt-stage"><div className="vt-stage-heading"><span className="vt-eyebrow">✦ SPEAK • LEARN • GROW</span><h1>Speak naturally.<br/><span className="gradient-text">Learn confidently.</span></h1><p>Gnani Prisma transcribes your voice; Gemini tutors in your selected language.</p></div>
        <div className={recording ? "vt-orb-area vt-recording" : "vt-orb-area"}><div className="vt-orb-ring"/><div className="vt-orb-ring vt-ring-two"/><button className="vt-orb" disabled={!selected || busy || transcribing || micStarting} onClick={() => void toggleRecording()} aria-label={recording ? "Stop recording" : "Start microphone recording"} aria-pressed={recording}><svg viewBox="0 0 24 24" width="45" height="45" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"/></svg></button></div>
        <div className={recording ? "vt-wave vt-wave-active" : "vt-wave"} aria-hidden="true">{Array.from({length: 35}, (_, index) => <i key={index} style={{ height: `${12 + Math.abs(Math.sin(index * 1.43)) * 38}px`, animationDelay: `${index * 37}ms` }}/>)}</div>
        <div className="vt-status" role="status">{micStarting ? "Requesting microphone permission…" : recording ? `Recording… ${recordingSeconds}s / 30s — tap the orb to stop` : transcribing ? "Transcribing with Gnani Prisma…" : speaking ? "Tutor audio is playing…" : speechLoading ? "Generating tutor audio with Gnani Timbre…" : busy ? "Gemini tutor is thinking…" : selected ? "Tap the orb to record a question" : "Choose a learning session first"}</div>
        {captureMetrics && <p className="vt-notice" role="status" aria-label="Last microphone capture quality">Last capture: {captureMetrics.durationSeconds.toFixed(1)} s · source {captureMetrics.sampleRateHz.toLocaleString()} Hz · output WAV 16 kHz mono PCM 16-bit · RMS {captureMetrics.rmsDbfs.toFixed(1)} dBFS · peak {captureMetrics.peakDbfs.toFixed(1)} dBFS · speech-level frames {captureMetrics.speechFramePercent.toFixed(1)}% · clipped {captureMetrics.clippedPercent.toFixed(2)}%. {captureMetrics.rmsDbfs < -42 ? "Input is quiet; check the selected Windows microphone and input level." : ""}</p>}
        {prismaDiagnostics && <p className="vt-notice" role="status" aria-label="Last Gnani Prisma request diagnostics">Gnani Prisma {prismaDiagnostics.provider_status} · {prismaDiagnostics.provider_model} · {prismaDiagnostics.provider_language_code}/{prismaDiagnostics.provider_format} · {prismaDiagnostics.provider_latency_ms} ms provider time · received WAV {prismaDiagnostics.audio_sample_rate_hz.toLocaleString()} Hz, {prismaDiagnostics.audio_channels} channel, {prismaDiagnostics.audio_bits_per_sample}-bit PCM.</p>}
        <label className="vt-autospeak"><input type="checkbox" checked={autoSpeak} onChange={event => setAutoSpeak(event.target.checked)}/> Generate and play tutor replies automatically</label>
        {speechLoading && !audioUrl && <button type="button" className="vt-stop-generation" onClick={() => stopPlayback()}>Cancel speech generation</button>}
        {localDemoAvailable && !demoMode && <button type="button" className="vt-demo-play" onClick={() => { const last = [...messages].reverse().find(item => item.role === "assistant"); if (last && selected) generateLocalDemo(last.content, selected, language); }}>Play local demo tone</button>}
        {audioUrl && <div className="vt-playback"><audio key={`${audioUrl}:${playbackElementKey}`} ref={audioRef} src={audioUrl} controls onPlay={() => startPlaybackSync(playbackElementKey)} onPause={() => pausePlaybackSync(playbackElementKey)} onEnded={() => completePlaybackSync(playbackElementKey)} onError={() => { if (!mounted.current) return; if (syncGenerationRef.current !== null) syncControllerRef.current?.fail(syncGenerationRef.current); else immersiveVoiceBridge.setState("error"); setSpeaking(false); if (!demoMode) void saveVoiceState({ playback_state: "error" }); }}>Your browser cannot play this WAV audio.</audio><button type="button" disabled={!speaking && !speechLoading} onClick={interruptSpeechForQuestion}>Interrupt tutor speech</button><button type="button" onClick={() => stopPlayback()}>Stop audio</button><small>{syncMode === "timestamped-visemes" ? "Timestamped viseme cues" : syncMode === "timestamped-phonemes-approximate" ? "Timestamped phonemes · approximate mouth shapes" : "Approximate audio-driven mouth animation · no phoneme alignment"} · {mouthViseme} mouth shape</small></div>}
        <div className="vt-stage-note">{demoMode ? "Local demo mode: generated tone only, no microphone recording, backend request, or Gnani speech." : "Microphone audio is converted to bounded mono PCM WAV and sent to the authenticated backend. Browser playback uses the WAV returned by Gnani Timbre."}</div>
        <div className="vt-new-topic"><form onSubmit={createSession}><label htmlFor="vt-topic">New learning topic</label><div><input id="vt-topic" value={topic} maxLength={200} onChange={event => setTopic(event.target.value)} placeholder="e.g. Everyday English" required/><button disabled={!topic.trim() || creating || busy || recording}>{creating ? "Creating…" : "+ Create"}</button></div></form></div>
      </section>
      <section className="vt-chat"><div className="vt-chat-header"><div><span className="vt-eyebrow">CONVERSATION TRANSCRIPT</span><h3>AI Tutor <span>✦</span></h3></div><span className="vt-chat-badge">{replyLatencyMs !== null ? `LAST TUTOR ROUND-TRIP · ${(replyLatencyMs / 1000).toFixed(1)} S` : "LATENCY MEASURES END-TO-END, NOT PROVIDER-ONLY"} · {providerConfigured === null ? "CHECKING VOICE PROVIDER…" : providerConfigured ? "GNANI CREDENTIALS CONFIGURED · LIVE CALLS ON DEMAND" : "GNANI UNAVAILABLE · TEXT CLASSROOM AVAILABLE"}</span></div>
        <div className="vt-transcript">{historyLoading ? <p className="vt-empty">Loading saved conversation…</p> : messages.length ? messages.map(message => <article key={message.id} className={message.role === "user" ? "vt-message vt-user" : "vt-message vt-ai"}><div className="vt-msg-label"><span>{message.role === "user" ? "YOU" : "✦ AI TUTOR"}</span>{message.role === "assistant" && <button disabled={speechLoading} onClick={() => void generateSpeech(message.content, selected, message.language || language)} aria-label="Generate or replay tutor speech">{speechLoading ? "Preparing…" : "▶ Listen / replay"}</button>}</div><p>{message.content}</p></article>) : <div className="vt-empty"><div>✦</div><h3>Your conversation starts here</h3><p>Record your question, review the Prisma transcript, then send it to your AI tutor.</p></div>}{busy && <p className="vt-thinking">✦ Tutor is preparing your reply…</p>}<div ref={scrollBottom}/></div>
        <div className="vt-compose">{error && <p className="vt-error" role="alert">{error}</p>}{notice && <p className="vt-notice" role="status">{notice}</p>}{pendingNavigation && <div className="vt-resume-prompt" role="group" aria-label="Voice navigation confirmation"><p>Voice navigation command recognized: {pendingNavigation.label}.</p><button type="button" onClick={() => { if (pendingNavigation.path === "__back__") navigate(-1); else navigate(pendingNavigation.path); setDraft(""); }}>Open {pendingNavigation.label}</button><button type="button" onClick={() => setDraft("")}>Dismiss</button></div>}{resumePrompt && <div className="vt-resume-prompt" role="group" aria-label="Lesson continuation"><p>Your question was answered. The lesson is paused at {Math.round((voiceState?.checkpoint_playback_ms || 0) / 1000)} seconds.</p><button type="button" onClick={() => void resumeCheckpoint()}>Resume lesson</button><button type="button" onClick={() => void dismissResume()}>Continue later</button></div>}{(draft || transcribing) && <p className="vt-interim">{transcribing ? "Processing microphone recording…" : "Prisma transcript — review or correct, then send"}</p>}<DesktopControlPanel transcript={draft} language={language}/><form onSubmit={sendMessage}><textarea aria-label="Prisma transcript or typed message" placeholder="Your Prisma transcript appears here. Review it or type a message…" value={draft} maxLength={4000} onChange={event => setDraft(event.target.value)} rows={3} disabled={busy || transcribing || recording || historyLoading}/><button disabled={!selected || !draft.trim() || busy || transcribing || recording || historyLoading}>{busy ? "Thinking…" : "Send to tutor ↗"}</button></form><small>Only the transcript you send enters Gemini and the saved session history. Microphone audio is not saved.</small></div>
        {!immersive && <PracticeAssessment sessionId={selected}/>}
      </section></div>
    </MainElement>
  </div>;
}
