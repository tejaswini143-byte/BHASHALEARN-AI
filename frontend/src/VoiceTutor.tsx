import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import { getSharedSessionContext } from "./sessionContext";
import { SessionModeNav } from "./SessionModeNav";
import { PracticeAssessment } from "./PracticeAssessment";
import { AvatarSyncController, type SyncMode } from "./avatarSync";
import "./voice.css";

type Language = "english" | "telugu" | "mixed";
type Session = { id: string; topic: string; language: Language; created_at: string };
type Message = { id: string; role: "user" | "assistant"; content: string; created_at: string };
type TutorReply = { reply: string; session_id: string; language: string; learning_level: string };
type Preferences = { preferred_language: Language; learning_level: string; learning_goal: string | null };
const headers = () => ({ Authorization: "Bearer " + getToken() });
function errorText(cause: unknown) { return cause instanceof Error ? cause.message : "Something went wrong."; }

function wavFromFloatChunks(chunks: Float32Array[], sampleRate: number): Blob {
  const inputCount = chunks.reduce((count, chunk) => count + chunk.length, 0);
  if (!inputCount || sampleRate < 1) throw new Error("No microphone audio was captured. Please try again.");
  const input = new Float32Array(inputCount);
  let inputOffset = 0;
  for (const chunk of chunks) { input.set(chunk, inputOffset); inputOffset += chunk.length; }
  const outputRate = 16000;
  const sampleCount = Math.max(1, Math.floor(inputCount * outputRate / sampleRate));
  if (44 + sampleCount * 2 > 10 * 1024 * 1024) throw new Error("Recording exceeds the 10 MB upload limit. Record a shorter clip.");
  const bytes = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(bytes);
  const writeText = (offset: number, value: string) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  writeText(0, "RIFF"); view.setUint32(4, bytes.byteLength - 8, true); writeText(8, "WAVE");
  writeText(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, outputRate, true); view.setUint32(28, outputRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); writeText(36, "data"); view.setUint32(40, sampleCount * 2, true);
  let offset = 44;
  const sourceSamplesPerOutput = sampleRate / outputRate;
  for (let index = 0; index < sampleCount; index += 1) {
    const start = index * sourceSamplesPerOutput;
    const end = Math.min(input.length, (index + 1) * sourceSamplesPerOutput);
    let weighted = 0;
    let weight = 0;
    for (let sourceIndex = Math.floor(start); sourceIndex < Math.ceil(end); sourceIndex += 1) {
      const overlap = Math.max(0, Math.min(end, sourceIndex + 1) - Math.max(start, sourceIndex));
      weighted += input[Math.min(sourceIndex, input.length - 1)] * overlap;
      weight += overlap;
    }
    const sample = weight ? weighted / weight : 0;
    const clipped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
    offset += 2;
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

export function VoiceTutor() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [student, setStudent] = useState<Student | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState("");
  const [language, setLanguage] = useState<Language>("mixed");
  const [preferences, setPreferences] = useState<Preferences>({ preferred_language: "mixed", learning_level: "beginner", learning_goal: null });
  const [topic, setTopic] = useState("");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [recording, setRecording] = useState(false);
  const [micStarting, setMicStarting] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [syncMode, setSyncMode] = useState<SyncMode>("silent");
  const [mouthViseme, setMouthViseme] = useState("sil");
  const [playbackRun, setPlaybackRun] = useState(0);
  const [speechLoading, setSpeechLoading] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioUrl, setAudioUrl] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
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
  const syncGenerationRef = useRef<number | null>(null);
  const audioLanguageRef = useRef<Language>("mixed");
  const mouthVisemeRef = useRef("sil");
  const playbackContextRef = useRef<AudioContext | null>(null);
  const playbackAnalyserRef = useRef<AnalyserNode | null>(null);
  const playbackSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const playbackSamplesRef = useRef<Uint8Array<ArrayBuffer> | null>(null);
  const syncControllerRef = useRef<AvatarSyncController | null>(null);
  if (!syncControllerRef.current) syncControllerRef.current = new AvatarSyncController(frame => {
    if (!mounted.current) return;
    setSyncMode(frame.mode);
    if (mouthVisemeRef.current !== frame.viseme) { mouthVisemeRef.current = frame.viseme; setMouthViseme(frame.viseme); }
  });
  const speechRequestRef = useRef<AbortController | null>(null);
  const recordingActive = useRef(false);
  const micRequestActive = useRef(false);
  const voiceTurnActive = useRef(false);
  const recordingTimer = useRef<number | null>(null);
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
    const token = getToken();
    if (!token) { signOut(); return; }
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
    }).catch(cause => { if (active) handleError(cause); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [handleError, signOut]);

  useEffect(() => {
    selectedRef.current = selected;
    const loadId = ++activeHistory.current;
    setMessages([]);
    if (!selected) { setHistoryLoading(false); return; }
    setHistoryLoading(true);
    getSharedSessionContext(selected)
      .then(context => {
        if (loadId !== activeHistory.current) return;
        setMessages(context.messages);
        setLanguage(context.preferred_language);
        setPreferences({ preferred_language: context.preferred_language, learning_level: context.learning_level, learning_goal: context.learning_goal });
      })
      .catch(cause => { if (loadId === activeHistory.current) handleError(cause); })
      .finally(() => { if (loadId === activeHistory.current) setHistoryLoading(false); });
  }, [selected, handleError]);

  useEffect(() => { scrollBottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, busy]);
  useEffect(() => {
    if (!audioUrl || !audioRef.current) return;
    syncGenerationRef.current = syncControllerRef.current!.begin({}, audioLanguageRef.current);
    void audioRef.current.play().catch(() => setNotice("Audio is ready. Press Play to start playback."));
  }, [audioUrl]);
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
      syncControllerRef.current?.cancel();
      audioRef.current?.pause();
      if (audioRef.current) audioRef.current.currentTime = 0;
      if (playbackSourceRef.current) { playbackSourceRef.current.disconnect(); playbackSourceRef.current = null; }
      if (playbackContextRef.current && playbackContextRef.current.state !== "closed") void playbackContextRef.current.close();
      audioCache.current.forEach(url => URL.revokeObjectURL(url));
    };
  }, [releaseMicrophone]);

  function stopPlayback() {
    speechRequestRef.current?.abort(); speechRequestRef.current = null;
    if (syncGenerationRef.current !== null) syncControllerRef.current?.cancel(syncGenerationRef.current);
    syncGenerationRef.current = null;
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.currentTime = 0; }
    setSpeaking(false); setSpeechLoading(false);
  }
  function startPlaybackSync() {
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
  }
  function pausePlaybackSync() {
    if (syncGenerationRef.current !== null && audioRef.current && !audioRef.current.ended) syncControllerRef.current?.pause(syncGenerationRef.current);
    setSpeaking(false);
  }
  function completePlaybackSync() {
    if (syncGenerationRef.current !== null) syncControllerRef.current?.complete(syncGenerationRef.current);
    setSpeaking(false);
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
    try {
      const updated = await request<Preferences>("/students/me/preferences", { method: "PUT", headers: headers(), body: JSON.stringify({ ...preferences, preferred_language: value }) });
      setPreferences(updated); setNotice("Tutor language updated. Your session and conversation remain unchanged.");
    } catch (cause) { setLanguage(previous); handleError(cause); }
  }

  async function transcribeWav(blob: Blob) {
    const sessionId = selected;
    if (!sessionId) return;
    setTranscribing(true); setError(""); setNotice("Sending PCM WAV to Gnani Prisma…");
    try {
      const form = new FormData(); form.append("audio", blob, "microphone.wav"); form.append("language", language);
      const response = await fetch(`/api/v1/voice/sessions/${encodeURIComponent(sessionId)}/transcribe`, { method: "POST", headers: headers(), body: form });
      const body = await response.json().catch(() => null) as { transcript?: unknown; detail?: unknown } | null;
      if (!response.ok) throw new ApiError(response.status, typeof body?.detail === "string" ? body.detail : "Speech transcription failed. You can type your question instead.");
      if (selectedRef.current !== sessionId) return;
      if (typeof body?.transcript !== "string" || !body.transcript.trim()) throw new Error("Prisma did not recognize speech. Try again or type your question.");
      setDraft(body.transcript); setNotice("Transcript ready. Review or correct it, then send it to your tutor.");
    } catch (cause) { handleError(cause); }
    finally { setTranscribing(false); }
  }

  async function finishRecording() {
    if (!recordingActive.current) return;
    voiceTurnActive.current = true;
    recordingActive.current = false; setRecording(false); setRecordingSeconds(0);
    setTranscribing(true);
    if (recordingTimer.current !== null) { window.clearInterval(recordingTimer.current); recordingTimer.current = null; }
    const context = contextRef.current;
    try {
      await releaseMicrophone();
      await transcribeWav(wavFromFloatChunks(chunksRef.current, context?.sampleRate || 48000));
    }
    catch (cause) { handleError(cause); }
    finally { setTranscribing(false); chunksRef.current = []; voiceTurnActive.current = false; }
  }

  async function toggleRecording() {
    if (recordingActive.current) { await finishRecording(); return; }
    setError(""); setNotice(""); stopPlayback();
    if (!selected || busy || transcribing || voiceTurnActive.current || micRequestActive.current) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioContext === "undefined") { setError("Microphone recording is unavailable in this browser. Type your question instead."); return; }
    micRequestActive.current = true; voiceTurnActive.current = true; setMicStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
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
      processor.onaudioprocess = event => chunksRef.current.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      source.connect(processor); processor.connect(mute); mute.connect(context.destination);
      recordingActive.current = true; setRecording(true);
      const started = Date.now();
      const timer = window.setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000); setRecordingSeconds(elapsed);
        if (elapsed >= 30) void finishRecording();
      }, 500);
      recordingTimer.current = timer;
    } catch {
      await releaseMicrophone(); recordingActive.current = false; voiceTurnActive.current = false; setRecording(false);
      setError("Microphone access was denied or could not start. Typed chat remains available.");
    } finally { micRequestActive.current = false; if (mounted.current) setMicStarting(false); }
  }

  async function generateSpeech(text: string, sessionId: string, mode: Language) {
    audioLanguageRef.current = mode;
    const cacheKey = `${sessionId}:${mode}:${text}`;
    const cached = audioCache.current.get(cacheKey);
    if (cached) {
      if (audioUrl === cached && audioRef.current) {
        audioRef.current.currentTime = 0;
        void audioRef.current.play().catch(() => setNotice("Audio is ready. Press Play to start playback."));
      } else { stopPlayback(); setAudioUrl(cached); }
      return;
    }
    stopPlayback(); setAudioUrl("");
    setSpeechLoading(true);
    const controller = new AbortController(); speechRequestRef.current = controller;
    try {
      const response = await fetch(`/api/v1/voice/sessions/${encodeURIComponent(sessionId)}/speech`, {
        method: "POST", headers: { ...headers(), "Content-Type": "application/json" }, body: JSON.stringify({ text, language: mode }), signal: controller.signal,
      });
      const blob = await readAudioResponse(response);
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob); audioCache.current.set(cacheKey, url); setAudioUrl(url); setNotice("Timbre audio is ready.");
      if (audioCache.current.size > 20) {
        const oldest = audioCache.current.keys().next().value;
        if (oldest) { URL.revokeObjectURL(audioCache.current.get(oldest)!); audioCache.current.delete(oldest); }
      }
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ApiError && cause.status === 401) handleError(cause);
      else setNotice("Tutor response is saved as text. Speech playback failed: " + errorText(cause));
    }
    finally { if (speechRequestRef.current === controller) speechRequestRef.current = null; setSpeechLoading(false); }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || !selected || busy || transcribing || recording || historyLoading) return;
    const sessionId = selected;
    setBusy(true); setError(""); setNotice(""); setDraft(""); stopPlayback();
    const optimistic: Message = { id: "pending-" + Date.now(), role: "user", content: message, created_at: new Date().toISOString() };
    setMessages(items => [...items, optimistic]);
    try {
      const result = await request<TutorReply>(`/tutor/sessions/${encodeURIComponent(sessionId)}/chat`, { method: "POST", headers: headers(), body: JSON.stringify({ message }) });
      if (selectedRef.current === sessionId) setMessages(items => [...items, { id: "reply-" + Date.now(), role: "assistant", content: result.reply, created_at: new Date().toISOString() }]);
      try {
        const saved = await request<Message[]>(`/sessions/${encodeURIComponent(sessionId)}/messages?limit=500`, { headers: headers() });
        if (selectedRef.current === sessionId) setMessages(saved);
      } catch { setNotice("Reply received, but saved history could not be refreshed."); }
      if (autoSpeak && selectedRef.current === sessionId) await generateSpeech(result.reply, sessionId, language);
    } catch (cause) {
      setMessages(items => items.filter(item => item.id !== optimistic.id)); setDraft(message); handleError(cause);
    } finally { setBusy(false); }
  }

  const current = sessions.find(session => session.id === selected);
  if (loading) return <main className="auth-screen"><p className="auth-wait">Opening your voice studio…</p></main>;
  if (!student) return <main className="auth-screen"><div className="cl-fatal"><h2>Voice studio unavailable</h2><p role="alert">{error}</p><button onClick={() => window.location.reload()}>Retry</button><button onClick={signOut}>Sign out</button></div></main>;
  return <div className="vt-app">
    <aside className={mobileMenu ? "vt-sidebar vt-sidebar-open" : "vt-sidebar"}>
      <Link className="vt-brand" to="/dashboard"><span>✦</span> BHASHA<strong>LEARN</strong> AI</Link>
      <Link to="/dashboard" className="vt-back">← Student dashboard</Link>
      <div className="vt-side-label">YOUR VOICE SESSIONS</div>
      <nav className="vt-sessions" aria-label="Voice learning sessions">{sessions.map(session => <button key={session.id} className={session.id === selected ? "vt-session-active" : ""} disabled={busy || transcribing || recording} onClick={() => chooseSession(session.id)}><span>◉</span><span><strong>{session.topic}</strong><small>{session.language} · {new Date(session.created_at).toLocaleDateString()}</small></span></button>)}{!sessions.length && <p>Start your first session to begin.</p>}</nav>
      <div className="vt-side-profile"><span>{student.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{student.display_name}</strong><small>Voice learner</small></div></div>
    </aside>
    <main className="vt-main">
      <header className="vt-topbar"><div><button className="vt-mobile-menu" onClick={() => setMobileMenu(!mobileMenu)} aria-label="Toggle sessions">☰</button><span className="vt-eyebrow">✦ VOICE LEARNING STUDIO</span><h2>{current?.topic || "Your voice classroom"}</h2></div><div className="vt-top-actions"><label>Tutor language <select value={language} disabled={recording || transcribing || busy} onChange={event => void changeLanguage(event.target.value as Language)}><option value="mixed">Telugu + English</option><option value="english">English</option><option value="telugu">తెలుగు</option></select></label></div><SessionModeNav sessionId={selected} active="voice"/></header>
      <div className="vt-layout"><section className="vt-stage"><div className="vt-stage-heading"><span className="vt-eyebrow">✦ SPEAK • LEARN • GROW</span><h1>Speak naturally.<br/><span className="gradient-text">Learn confidently.</span></h1><p>Gnani Prisma transcribes your voice; Gemini tutors in your selected language.</p></div>
        <div className={recording ? "vt-orb-area vt-recording" : "vt-orb-area"}><div className="vt-orb-ring"/><div className="vt-orb-ring vt-ring-two"/><button className="vt-orb" disabled={!selected || busy || transcribing || micStarting} onClick={() => void toggleRecording()} aria-label={recording ? "Stop recording" : "Start microphone recording"} aria-pressed={recording}><svg viewBox="0 0 24 24" width="45" height="45" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"/></svg></button></div>
        <div className={recording ? "vt-wave vt-wave-active" : "vt-wave"} aria-hidden="true">{Array.from({length: 35}, (_, index) => <i key={index} style={{ height: `${12 + Math.abs(Math.sin(index * 1.43)) * 38}px`, animationDelay: `${index * 37}ms` }}/>)}</div>
        <div className="vt-status" role="status">{micStarting ? "Requesting microphone permission…" : recording ? `Recording… ${recordingSeconds}s / 30s — tap the orb to stop` : transcribing ? "Transcribing with Gnani Prisma…" : speaking ? "Tutor audio is playing…" : speechLoading ? "Generating tutor audio with Gnani Timbre…" : busy ? "Gemini tutor is thinking…" : selected ? "Tap the orb to record a question" : "Choose a learning session first"}</div>
        <label className="vt-autospeak"><input type="checkbox" checked={autoSpeak} onChange={event => setAutoSpeak(event.target.checked)}/> Generate and play tutor replies automatically</label>
        {speechLoading && !audioUrl && <button type="button" className="vt-stop-generation" onClick={stopPlayback}>Cancel speech generation</button>}
        {audioUrl && <div className="vt-playback"><audio ref={audioRef} src={audioUrl} controls onPlay={startPlaybackSync} onPause={pausePlaybackSync} onEnded={completePlaybackSync} onError={() => { if (syncGenerationRef.current !== null) syncControllerRef.current?.fail(syncGenerationRef.current); setSpeaking(false); }}>Your browser cannot play this WAV audio.</audio><button type="button" onClick={stopPlayback}>Stop audio</button><small>{syncMode === "timestamped-visemes" ? "Timestamped viseme cues" : syncMode === "timestamped-phonemes-approximate" ? "Timestamped phonemes · approximate mouth shapes" : "Approximate audio-driven mouth animation · no phoneme alignment"} · {mouthViseme} mouth shape</small></div>}
        <div className="vt-stage-note">Microphone audio is converted to bounded mono PCM WAV and sent to the authenticated backend. Browser playback uses the WAV returned by Gnani Timbre.</div>
        <div className="vt-new-topic"><form onSubmit={createSession}><label htmlFor="vt-topic">New learning topic</label><div><input id="vt-topic" value={topic} maxLength={200} onChange={event => setTopic(event.target.value)} placeholder="e.g. Everyday English" required/><button disabled={!topic.trim() || creating || busy || recording}>{creating ? "Creating…" : "+ Create"}</button></div></form></div>
      </section>
      <section className="vt-chat"><div className="vt-chat-header"><div><span className="vt-eyebrow">CONVERSATION TRANSCRIPT</span><h3>AI Tutor <span>✦</span></h3></div><span className="vt-chat-badge">PRISMA + GEMINI + TIMBRE</span></div>
        <div className="vt-transcript">{historyLoading ? <p className="vt-empty">Loading saved conversation…</p> : messages.length ? messages.map(message => <article key={message.id} className={message.role === "user" ? "vt-message vt-user" : "vt-message vt-ai"}><div className="vt-msg-label"><span>{message.role === "user" ? "YOU" : "✦ AI TUTOR"}</span>{message.role === "assistant" && <button disabled={speechLoading} onClick={() => void generateSpeech(message.content, selected, language)} aria-label="Generate or replay tutor speech">{speechLoading ? "Preparing…" : "▶ Listen / replay"}</button>}</div><p>{message.content}</p></article>) : <div className="vt-empty"><div>✦</div><h3>Your conversation starts here</h3><p>Record your question, review the Prisma transcript, then send it to your AI tutor.</p></div>}{busy && <p className="vt-thinking">✦ Tutor is preparing your reply…</p>}<div ref={scrollBottom}/></div>
        <div className="vt-compose">{error && <p className="vt-error" role="alert">{error}</p>}{notice && <p className="vt-notice" role="status">{notice}</p>}{(draft || transcribing) && <p className="vt-interim">{transcribing ? "Processing microphone recording…" : "Prisma transcript — review or edit before sending"}</p>}<form onSubmit={sendMessage}><textarea aria-label="Prisma transcript or typed message" placeholder="Your Prisma transcript appears here. Review it or type a message…" value={draft} maxLength={4000} onChange={event => setDraft(event.target.value)} rows={3} disabled={busy || transcribing || recording || historyLoading}/><button disabled={!selected || !draft.trim() || busy || transcribing || recording || historyLoading}>{busy ? "Thinking…" : "Send to tutor ↗"}</button></form><small>Only the transcript you send enters Gemini and the saved session history. Microphone audio is not saved.</small></div>
        <PracticeAssessment sessionId={selected}/>
      </section></div>
    </main>
  </div>;
}
