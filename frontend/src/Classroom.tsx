import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import "./classroom.css";

type Language = "telugu" | "english" | "mixed";
type Session = { id: string; topic: string; language: Language; created_at: string };
type Message = { id: string; role: "user" | "assistant"; content: string; created_at: string };
type TutorReply = { session_id: string; reply: string; language: string; learning_level: string };
type Preferences = { preferred_language: Language; learning_level: string; learning_goal: string | null };
const languages: Language[] = ["mixed", "english", "telugu"];
const examples = ["Explain this in simple words", "Give me an example", "Quiz me on this topic"];
function formatTime(date: string) { return new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

export function Classroom() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [student, setStudent] = useState<Student | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<Preferences>({ preferred_language: "mixed", learning_level: "beginner", learning_goal: null });
  const [language, setLanguage] = useState<Language>("mixed");
  const [topic, setTopic] = useState("");
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const activeLoad = useRef(0);
  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);
  const headers = useCallback(() => ({ Authorization: "Bearer " + getToken() }), []);
  const report = useCallback((cause: unknown) => {
    if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
    setError(cause instanceof Error ? cause.message : "Something went wrong. Please retry.");
  }, [signOut]);

  useEffect(() => {
    let live = true;
    const token = getToken();
    if (!token) { signOut(); return; }
    (async () => {
      try {
        const [profile, list, preferences] = await Promise.all([
          getCurrentStudent(token),
          request<Session[]>("/sessions?limit=100", { headers: { Authorization: "Bearer " + token } }),
          request<Preferences>("/students/me/preferences", { headers: { Authorization: "Bearer " + token } }),
        ]);
        if (!live) return;
        setStudent(profile); setSessions(list); setPrefs(preferences); setLanguage(preferences.preferred_language);
        const requested = params.get("session");
        if (requested && list.some(item => item.id === requested)) setSelected(requested);
        else if (list.length) setSelected(list[0].id);
        else setShowCreate(true);
      } catch (cause) { if (live) report(cause); }
      finally { if (live) setLoading(false); }
    })();
    return () => { live = false; };
    // Read initial deep-link once; subsequent selection is handled locally.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report]);

  useEffect(() => {
    const loadId = ++activeLoad.current;
    setMessages([]); setError("");
    if (!selected) { setHistoryLoading(false); return; }
    setHistoryLoading(true);
    request<Message[]>(`/sessions/${encodeURIComponent(selected)}/messages?limit=500`, { headers: headers() })
      .then(data => { if (activeLoad.current === loadId) setMessages(data); })
      .catch(cause => { if (activeLoad.current === loadId) report(cause); })
      .finally(() => { if (activeLoad.current === loadId) setHistoryLoading(false); });
  }, [selected, headers, report]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, busy, historyLoading]);
  const current = sessions.find(s => s.id === selected);

  function selectSession(id: string) { if (busy) return; setSelected(id); setParams({ session: id }); setSidebarOpen(false); setNotice(""); setShowCreate(false); }
  async function createSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!topic.trim() || creating || busy) return;
    setCreating(true); setError(""); setNotice("");
    try {
      const session = await request<Session>("/sessions", { method: "POST", headers: headers(), body: JSON.stringify({ topic: topic.trim(), language }) });
      setSessions(items => [session, ...items]); setTopic(""); selectSession(session.id);
    } catch (cause) { report(cause); } finally { setCreating(false); }
  }
  async function updateLanguage(value: Language) {
    if (busy) return;
    const previous = language;
    setLanguage(value); setNotice(""); setError("");
    try {
      const updated = await request<Preferences>("/students/me/preferences", { method: "PUT", headers: headers(), body: JSON.stringify({ ...prefs, preferred_language: value }) });
      setPrefs(updated);
      setNotice("Tutor language preference updated for future replies.");
    } catch (cause) { setLanguage(previous); report(cause); }
  }
  async function sendMessage(event?: FormEvent<HTMLFormElement>, suggestion?: string) {
    event?.preventDefault();
    const message = (suggestion ?? draft).trim();
    if (!selected || !message || busy || historyLoading) return;
    const sessionId = selected;
    setBusy(true); setError(""); setNotice(""); setDraft("");
    const optimistic: Message = { id: "pending-" + Date.now(), role: "user", content: message, created_at: new Date().toISOString() };
    setMessages(items => [...items, optimistic]);
    try {
      await request<TutorReply>(`/tutor/sessions/${encodeURIComponent(sessionId)}/chat`, { method: "POST", headers: headers(), body: JSON.stringify({ message }) });
      const saved = await request<Message[]>(`/sessions/${encodeURIComponent(sessionId)}/messages?limit=500`, { headers: headers() });
      if (activeLoad.current && selected === sessionId) setMessages(saved);
    } catch (cause) {
      setMessages(items => items.filter(item => item.id !== optimistic.id));
      setDraft(message);
      report(cause);
    } finally { setBusy(false); }
  }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); if (!busy) void sendMessage(); }
  }
  const visibleSessions = sessions.filter(s => s.topic.toLowerCase().includes(search.toLowerCase()));
  if (loading) return <main className="auth-screen"><p className="auth-wait">Preparing your AI classroom…</p></main>;
  if (!student) return <main className="auth-screen"><div className="cl-fatal"><h2>Classroom unavailable</h2><p role="alert">{error}</p><button onClick={() => window.location.reload()}>Retry</button><button onClick={signOut}>Sign out</button></div></main>;
  return <div className="cl-app">
    <aside className={sidebarOpen ? "cl-sidebar cl-sidebar-open" : "cl-sidebar"}>
      <Link to="/dashboard" className="cl-brand"><span className="cl-brand-icon">✦</span> BHASHA<span>LEARN</span><small> AI</small></Link>
      <Link className="cl-back" to="/dashboard">← Back to dashboard</Link><Link className="cl-back" to="/voice">◉ Open voice studio ↗</Link>
      <button className="cl-new" onClick={() => { setShowCreate(true); setSidebarOpen(false); }} disabled={busy}>＋ New learning session</button>
      <label className="cl-search">⌕ <input aria-label="Search learning sessions" placeholder="Search your sessions…" value={search} onChange={e => setSearch(e.target.value)}/></label>
      <div className="cl-side-label">YOUR CONVERSATIONS</div>
      <nav className="cl-session-nav" aria-label="Learning sessions">{visibleSessions.length ? visibleSessions.map(s => <button key={s.id} disabled={busy} className={selected === s.id && !showCreate ? "cl-session-active" : ""} onClick={() => selectSession(s.id)}><span className="cl-session-icon">✧</span><span><strong>{s.topic}</strong><small>{s.language} · {new Date(s.created_at).toLocaleDateString()}</small></span></button>) : <p className="cl-side-empty">{sessions.length ? "No matching sessions" : "Your learning sessions will appear here."}</p>}</nav>
      <div className="cl-side-footer"><span className="cl-avatar">{student.display_name.slice(0, 1).toUpperCase()}</span><span><strong>{student.display_name}</strong><small>AI learning companion</small></span></div>
    </aside>
    <section className="cl-workspace">
      <header className="cl-header"><div className="cl-heading"><button className="cl-menu" aria-label="Toggle session sidebar" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(!sidebarOpen)}>☰</button><div><small>✦ AI CLASSROOM</small><strong>{showCreate ? "New learning session" : current?.topic || "Choose a topic"}</strong></div></div><div className="cl-header-actions"><span className="cl-live"><i/> TEXT TUTOR</span><label className="cl-language">Tutor language <select value={language} disabled={busy} onChange={e => void updateLanguage(e.target.value as Language)}>{languages.map(lang => <option key={lang} value={lang}>{lang === "mixed" ? "Telugu + English" : lang === "english" ? "English" : "తెలుగు"}</option>)}</select></label><button className="cl-signout" onClick={signOut}>Sign out ↗</button></div></header>
      {showCreate || !current ? <main className="cl-create"><div className="cl-create-art">✦</div><span className="cl-kicker">YOUR NEXT DISCOVERY STARTS HERE</span><h1>What shall we <span className="gradient-text">learn today?</span></h1><p>Pick a topic and your AI tutor will guide you step by step, in your preferred language.</p><form onSubmit={createSession}><label htmlFor="cl-topic">Learning topic</label><input id="cl-topic" maxLength={200} required value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g. English conversation, algebra, Telugu vocabulary"/><button disabled={creating || !topic.trim()}>{creating ? "Creating…" : "Start classroom ↗"}</button></form>{error && <p className="cl-error" role="alert">{error}</p>}</main> :
      <><div className="cl-conversation" aria-label="AI tutor conversation" aria-live="polite">{historyLoading ? <p className="cl-system">Loading conversation…</p> : messages.length === 0 ? <div className="cl-intro"><div className="cl-tutor-orb">✦</div><span className="cl-kicker">MEET YOUR AI LEARNING COMPANION</span><h1>Ready to explore <span className="gradient-text">{current.topic}?</span></h1><p>Ask a question, request a simple explanation, or try a quick quiz. Your conversation will be saved to this session.</p><div className="cl-suggestions">{examples.map(example => <button key={example} disabled={busy} onClick={() => void sendMessage(undefined, example)}>{example} ↗</button>)}</div></div> : <div className="cl-messages">{messages.map(m => <article className={m.role === "user" ? "cl-message cl-user" : "cl-message cl-assistant"} key={m.id}><div className="cl-message-avatar">{m.role === "user" ? student.display_name.slice(0,1).toUpperCase() : "✦"}</div><div className="cl-message-content"><div className="cl-message-meta"><strong>{m.role === "user" ? "You" : "BHASHALEARN Tutor"}</strong><span>{formatTime(m.created_at)}</span></div><div className="cl-bubble">{m.content}</div></div></article>)}{busy && <div className="cl-thinking"><span>✦</span> Tutor is preparing a reply… <i/><i/><i/></div>}</div>}<div ref={bottom}/></div><div className="cl-composer-wrap">{error && <p className="cl-error" role="alert">{error}</p>}{notice && <p className="cl-notice" role="status">{notice}</p>}<form className="cl-composer" onSubmit={event => void sendMessage(event)}><textarea aria-label="Message your AI tutor" value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={keyDown} placeholder="Ask your tutor anything… (Enter to send, Shift+Enter for new line)" maxLength={4000} rows={2} disabled={busy || historyLoading}/><button aria-label="Send message" disabled={!draft.trim() || busy || historyLoading} type="submit">➤</button></form><p className="cl-disclaimer">AI-generated explanations may contain mistakes. Voice and visual lessons arrive in later tasks.</p></div></>}
    </section>
  </div>;
}
