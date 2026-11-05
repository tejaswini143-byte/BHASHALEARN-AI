import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import "./voice.css";

type Language = "english" | "telugu" | "mixed";
type Session = { id: string; topic: string; language: Language; created_at: string };
type Message = { id: string; role: "user" | "assistant"; content: string; created_at: string };
type TutorReply = { reply: string; session_id: string; language: string; learning_level: string };
type RecognitionResult = { results: ArrayLike<ArrayLike<{ transcript: string }>>; resultIndex: number };
type SpeechRecognitionLike = { lang: string; continuous: boolean; interimResults: boolean; onresult: ((event: RecognitionResult) => void) | null; onerror: ((event: { error: string }) => void) | null; onend: (() => void) | null; start(): void; stop(): void; abort(): void };
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
type SpeechWindow = Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
const locale = (lang: Language) => lang === "telugu" ? "te-IN" : "en-IN";
const headers = () => ({ Authorization: "Bearer " + getToken() });
function errorText(cause: unknown) { return cause instanceof Error ? cause.message : "Something went wrong."; }

export function VoiceTutor() {
  const navigate = useNavigate();
  const [student, setStudent] = useState<Student | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState("");
  const [language, setLanguage] = useState<Language>("mixed");
  const [topic, setTopic] = useState("");
  const [draft, setDraft] = useState("");
  const [interim, setInterim] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [recording, setRecording] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mobileMenu, setMobileMenu] = useState(false);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const scrollBottom = useRef<HTMLDivElement>(null);
  const activeHistory = useRef(0);
  const selectedRef = useRef("");
  const listeningRef = useRef(false);
  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);
  const handleError = useCallback((cause: unknown) => { if (cause instanceof ApiError && cause.status === 401) { signOut(); return; } setError(errorText(cause)); }, [signOut]);
  const stopVoice = useCallback(() => {
    listeningRef.current = false;
    recognition.current?.abort(); recognition.current = null;
    setRecording(false); setInterim("");
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) { signOut(); return; }
    Promise.all([getCurrentStudent(token), request<Session[]>("/sessions?limit=100", { headers: { Authorization: "Bearer " + token } })])
      .then(([profile, list]) => { if (!active) return; setStudent(profile); setSessions(list); if (list.length) setSelected(list[0].id); })
      .catch(cause => { if (active) handleError(cause); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [handleError, signOut]);

  useEffect(() => {
    selectedRef.current = selected;
    const loadId = ++activeHistory.current;
    setMessages([]);
    if (!selected) { setHistoryLoading(false); return; }
    setHistoryLoading(true);
    request<Message[]>(`/sessions/${encodeURIComponent(selected)}/messages?limit=500`, { headers: headers() })
      .then(data => { if (loadId === activeHistory.current) setMessages(data); })
      .catch(cause => { if (loadId === activeHistory.current) handleError(cause); })
      .finally(() => { if (loadId === activeHistory.current) setHistoryLoading(false); });
  }, [selected, handleError]);
  useEffect(() => { scrollBottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, busy]);
  useEffect(() => () => { listeningRef.current = false; recognition.current?.abort(); if ("speechSynthesis" in window) window.speechSynthesis.cancel(); }, []);

  function chooseSession(id: string) { if (busy) return; stopVoice(); setError(""); setNotice(""); setSelected(id); setMobileMenu(false); }
  async function createSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!topic.trim() || creating) return;
    setCreating(true); setError("");
    try {
      const session = await request<Session>("/sessions", { method: "POST", headers: headers(), body: JSON.stringify({ topic: topic.trim(), language }) });
      setSessions(list => [session, ...list]); setTopic(""); chooseSession(session.id);
    } catch (cause) { handleError(cause); } finally { setCreating(false); }
  }
  function startRecording() {
    setError(""); setNotice("");
    if (recording) { listeningRef.current = false; recognition.current?.stop(); setRecording(false); return; }
    const speechWindow = window as SpeechWindow;
    const Constructor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Constructor) { setError("Speech recognition is unavailable in this browser. Use Chrome or Edge, or type your message."); return; }
    if (!selected) { setError("Create or select a learning session first."); return; }
    if (busy) return;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
    const instance = new Constructor();
    instance.lang = locale(language); instance.continuous = false; instance.interimResults = true;
    instance.onresult = event => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) transcript += event.results[i][0].transcript;
      setInterim(transcript);
      setDraft(transcript);
    };
    instance.onerror = event => { if (listeningRef.current) setError("Microphone recognition error: " + event.error + ". You can type instead."); listeningRef.current = false; setRecording(false); };
    instance.onend = () => { listeningRef.current = false; setRecording(false); setInterim(""); };
    try { recognition.current = instance; listeningRef.current = true; instance.start(); setRecording(true); }
    catch { listeningRef.current = false; setError("Could not start the microphone. Check browser permissions."); }
  }
  function speak(text: string) {
    if (!("speechSynthesis" in window)) { setNotice("Speech playback is not available in this browser."); return; }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = locale(language); utterance.rate = .92;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }
  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || !selected || busy || historyLoading) return;
    const sessionId = selected;
    stopVoice(); setBusy(true); setError(""); setNotice(""); setDraft("");
    const optimistic: Message = { id: "pending-" + Date.now(), role: "user", content: message, created_at: new Date().toISOString() };
    setMessages(items => [...items, optimistic]);
    try {
      const result = await request<TutorReply>(`/tutor/sessions/${encodeURIComponent(sessionId)}/chat`, { method: "POST", headers: headers(), body: JSON.stringify({ message }) });
      if (selectedRef.current === sessionId) {
        setMessages(items => [...items, { id: "reply-" + Date.now(), role: "assistant", content: result.reply, created_at: new Date().toISOString() }]);
        if (autoSpeak) speak(result.reply);
      }
      try {
        const saved = await request<Message[]>(`/sessions/${encodeURIComponent(sessionId)}/messages?limit=500`, { headers: headers() });
        if (selectedRef.current === sessionId) setMessages(saved);
      } catch { setNotice("Reply received, but saved history could not be refreshed."); }
    } catch (cause) {
      setMessages(items => items.filter(item => item.id !== optimistic.id));
      setDraft(message); handleError(cause);
    } finally { setBusy(false); }
  }
  const current = sessions.find(s => s.id === selected);
  if (loading) return <main className="auth-screen"><p className="auth-wait">Opening your voice studio…</p></main>;
  if (!student) return <main className="auth-screen"><div className="cl-fatal"><h2>Voice studio unavailable</h2><p role="alert">{error}</p><button onClick={() => window.location.reload()}>Retry</button><button onClick={signOut}>Sign out</button></div></main>;
  return <div className="vt-app">
    <aside className={mobileMenu ? "vt-sidebar vt-sidebar-open" : "vt-sidebar"}>
      <Link className="vt-brand" to="/dashboard"><span>✦</span> BHASHA<strong>LEARN</strong> AI</Link>
      <Link to="/dashboard" className="vt-back">← Student dashboard</Link>
      <div className="vt-side-label">YOUR VOICE SESSIONS</div>
      <nav className="vt-sessions" aria-label="Voice learning sessions">{sessions.map(s => <button key={s.id} className={selected === s.id ? "vt-session-active" : ""} disabled={busy} onClick={() => chooseSession(s.id)}><span>◉</span><span><strong>{s.topic}</strong><small>{s.language} · {new Date(s.created_at).toLocaleDateString()}</small></span></button>)}{!sessions.length && <p>Start your first session to begin.</p>}</nav>
      <div className="vt-side-profile"><span>{student.display_name.slice(0,1).toUpperCase()}</span><div><strong>{student.display_name}</strong><small>Voice learner</small></div></div>
    </aside>
    <main className="vt-main">
      <header className="vt-topbar"><div><button className="vt-mobile-menu" onClick={() => setMobileMenu(!mobileMenu)} aria-label="Toggle sessions">☰</button><span className="vt-eyebrow">✦ VOICE LEARNING STUDIO</span><h2>{current?.topic || "Your voice classroom"}</h2></div><div className="vt-top-actions"><label>Recognition language <select value={language} disabled={recording || busy} onChange={e => setLanguage(e.target.value as Language)}><option value="mixed">Telugu + English*</option><option value="english">English</option><option value="telugu">తెలుగు</option></select></label><Link to="/classroom">Text classroom ↗</Link></div></header>
      <div className="vt-layout"><section className="vt-stage"><div className="vt-stage-heading"><span className="vt-eyebrow">✦ SPEAK • LEARN • GROW</span><h1>Speak naturally.<br/><span className="gradient-text">Learn confidently.</span></h1><p>Practice with your AI tutor through speech-to-text and spoken replies.</p></div>
        <div className={recording ? "vt-orb-area vt-recording" : "vt-orb-area"}><div className="vt-orb-ring"/><div className="vt-orb-ring vt-ring-two"/><button className="vt-orb" disabled={!selected || busy} onClick={startRecording} aria-label={recording ? "Stop recording" : "Start microphone recognition"} aria-pressed={recording}><svg viewBox="0 0 24 24" width="45" height="45" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"/></svg></button></div>
        <div className={recording ? "vt-wave vt-wave-active" : "vt-wave"} aria-hidden="true">{Array.from({length:35},(_,i) => <i key={i} style={{height: `${12 + Math.abs(Math.sin(i * 1.43)) * 38}px`, animationDelay: `${i * 37}ms` }}/>)}</div>
        <div className="vt-status" role="status">{recording ? "Listening… tap the orb to stop" : speaking ? "Tutor is speaking…" : busy ? "Tutor is thinking…" : selected ? "Tap the orb to speak" : "Choose a learning session first"}</div>
        {interim && <p className="vt-interim">Recognized: {interim}</p>}
        <label className="vt-autospeak"><input type="checkbox" checked={autoSpeak} onChange={e => setAutoSpeak(e.target.checked)}/> Read tutor replies aloud</label>
        <div className="vt-stage-note">Browser speech recognition and speech synthesis • Not Gnani Prisma/Timbre yet<br/>*Mixed mode uses English (India) recognition; Telugu words may be inaccurate.</div>
        <div className="vt-new-topic"><form onSubmit={createSession}><label htmlFor="vt-topic">New learning topic</label><div><input id="vt-topic" value={topic} maxLength={200} onChange={e => setTopic(e.target.value)} placeholder="e.g. Everyday English" required/><button disabled={!topic.trim() || creating || busy}>{creating ? "Creating…" : "＋ Create"}</button></div></form></div>
      </section>
      <section className="vt-chat"><div className="vt-chat-header"><div><span className="vt-eyebrow">CONVERSATION TRANSCRIPT</span><h3>AI Tutor <span>✦</span></h3></div><span className="vt-chat-badge">TEXT + BROWSER VOICE</span></div>
        <div className="vt-transcript">{historyLoading ? <p className="vt-empty">Loading saved conversation…</p> : messages.length ? messages.map(m => <article key={m.id} className={m.role === "user" ? "vt-message vt-user" : "vt-message vt-ai"}><div className="vt-msg-label"><span>{m.role === "user" ? "YOU" : "✦ AI TUTOR"}</span>{m.role === "assistant" && <button onClick={() => speak(m.content)} aria-label="Read tutor message aloud">▶ Listen</button>}</div><p>{m.content}</p></article>) : <div className="vt-empty"><div>✦</div><h3>Your conversation starts here</h3><p>Speak into the microphone, review the recognized text, then send it to your AI tutor.</p></div>}{busy && <p className="vt-thinking">✦ Tutor is preparing your reply…</p>}<div ref={scrollBottom}/></div>
        <div className="vt-compose">{error && <p className="vt-error" role="alert">{error}</p>}{notice && <p className="vt-notice" role="status">{notice}</p>}<form onSubmit={sendMessage}><textarea aria-label="Recognized speech or typed message" placeholder="Your recognized words appear here. Review or type your question…" value={draft} maxLength={4000} onChange={e => setDraft(e.target.value)} rows={3} disabled={busy || historyLoading}/><button disabled={!selected || !draft.trim() || busy || historyLoading}>Send to tutor ↗</button></form><small>Audio is handled by your browser; only the text you send is submitted to the tutor API.</small></div>
      </section></div>
    </main>
  </div>;
}
