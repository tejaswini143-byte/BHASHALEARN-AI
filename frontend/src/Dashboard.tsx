import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import "./dashboard.css";

type Progress = { id: string; topic: string; mastery_score: number; attempts: number; evidence_attempts: number; evidence_status: string; correct_attempts: number; incorrect_attempts: number; recommendation: string; updated_at: string };
type Session = { id: string; topic: string; language: string; created_at: string };
type Preferences = { preferred_language: string; learning_level: string; learning_goal: string | null };
type DashboardData = { student: Student; progress: Progress[]; sessions: Session[]; preferences: Preferences };
const authHeaders = (token: string) => ({ Authorization: "Bearer " + token });
const dateLabel = (value: string) => new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });

function Ring({ value }: { value: number }) {
  const percent = Math.max(0, Math.min(100, value));
  return <div className="db-ring" style={{ background: `conic-gradient(#64e2fa ${percent}%,#293459 0)` }}><div><strong>{Math.round(percent)}%</strong><small>avg mastery</small></div></div>;
}
function ProgressBars({ items }: { items: Progress[] }) {
  return <div className="db-bars">{items.length ? items.slice(0, 6).map(item => <div className="db-bar-row" key={item.id}><div className="db-bar-label"><span>{item.topic}</span><b>{item.evidence_attempts > 0 ? `${Math.round(item.mastery_score)}%` : "Not assessed"}</b></div><div className="db-bar-track"><div style={{ width: `${item.evidence_attempts > 0 ? Math.max(0,Math.min(100,item.mastery_score)) : 0}%` }}/></div></div>) : <p className="db-empty">No mastery data yet. Your learning progress will appear here after activities are recorded.</p>}</div>;
}

export function ProtectedDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [search, setSearch] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState("");
  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);

  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) { navigate("/login", { replace: true }); return; }
    setLoading(true); setError("");
    (async () => {
      try {
        const headers = authHeaders(token);
        const student = await getCurrentStudent(token);
        const [progress, sessions, preferences] = await Promise.all([
          request<Progress[]>("/progress?limit=100", { headers }),
          request<Session[]>("/sessions?limit=20", { headers }),
          request<Preferences>("/students/me/preferences", { headers }),
        ]);
        if (active) setData({ student, progress, sessions, preferences });
      } catch (cause) {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
        setError(cause instanceof Error ? cause.message : "Could not load your dashboard.");
      } finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [navigate, refresh, signOut]);

  async function createSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getToken();
    if (!token || !topic.trim() || creating) return;
    setCreating(true); setNotice("");
    try {
      await request<Session>("/sessions", { method: "POST", headers: authHeaders(token), body: JSON.stringify({ topic: topic.trim(), language: data?.preferences.preferred_language || "mixed" }) });
      setTopic(""); setRefresh(n => n + 1); setNotice("Session created. Open AI Classroom to begin chatting with your tutor.");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
      setNotice(cause instanceof Error ? cause.message : "Could not create session.");
    } finally { setCreating(false); }
  }

  if (loading && !data) return <main className="auth-screen"><p className="auth-wait">Loading your learning space…</p></main>;
  if (!data) return <main className="auth-screen"><div className="db-error"><h2>Dashboard unavailable</h2><p role="alert">{error}</p><button onClick={() => setRefresh(n => n + 1)}>Try again</button><button onClick={signOut}>Sign out</button></div></main>;

  const { student, progress, sessions, preferences } = data;
  const assessedProgress = progress.filter(item => item.evidence_attempts > 0);
  const average = assessedProgress.length ? assessedProgress.reduce((sum, p) => sum + p.mastery_score, 0) / assessedProgress.length : 0;
  const attempts = progress.reduce((sum, p) => sum + p.evidence_attempts, 0);
  const filteredSessions = sessions.filter(s => s.topic.toLowerCase().includes(search.toLowerCase()));
  return <div className="db-app">
    <aside className={menuOpen ? "db-sidebar db-sidebar-open" : "db-sidebar"}>
      <Link to="/" className="db-logo"><span className="brand-symbol">✦</span><span>BHASHA<strong>LEARN</strong><small> AI</small></span></Link>
      <div className="db-nav-label">YOUR WORKSPACE</div>
      <nav className="db-nav" aria-label="Dashboard navigation"><a href="#overview" className="db-nav-active" onClick={() => setMenuOpen(false)}>◈ <span>Overview</span></a><a href="#progress" onClick={() => setMenuOpen(false)}>◷ <span>My progress</span></a><a href="#sessions" onClick={() => setMenuOpen(false)}>▤ <span>Learning sessions</span></a><a href="#start" onClick={() => setMenuOpen(false)}>✧ <span>Start learning</span></a></nav>
      <div className="db-nav-label">LEARNING STUDIOS</div><div className="db-nav db-upcoming"><Link to="/voice">◉ &nbsp; Voice classroom <small>OPEN ↗</small></Link><Link to="/visual">◇ &nbsp; Visual studio <small>OPEN ↗</small></Link><Link to="/chat">▣ &nbsp; AI chat <small>OPEN ↗</small></Link><Link to="/documents">▤ &nbsp; Documents <small>OPEN ↗</small></Link></div>
      <div className="db-sidebar-bottom"><div className="db-profile-dot">{student.display_name.slice(0,1).toUpperCase()}</div><div className="db-profile-name"><strong>{student.display_name}</strong><small>{student.email}</small></div></div>
    </aside>
    <div className="db-main">
      <header className="db-topbar"><button className="db-menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen} aria-label="Toggle sidebar">☰</button><span className="db-breadcrumb">Workspace <span>/</span> Overview</span><div className="db-top-actions"><span className="db-online"><i/> Learning space</span><button onClick={() => setRefresh(n => n + 1)} disabled={loading} aria-label="Refresh dashboard">↻ Refresh</button><button onClick={signOut}>Sign out ↗</button></div></header>
      <main id="overview" className="db-content">
        <section className="db-hero"><div><span className="db-eyebrow">✦ YOUR PERSONAL LEARNING UNIVERSE</span><h1>Welcome back, <span className="gradient-text">{student.display_name.split(" ")[0]}.</span></h1><p>Every new word is progress. Keep exploring, speaking, and growing.</p><Link className="db-hero-cta" to="/classroom">Open AI Classroom ↗</Link></div><div className="db-hero-art" aria-hidden="true"><div className="db-art-ring db-art-ring-one"/><div className="db-art-ring db-art-ring-two"/><div className="db-art-core">✦</div><span className="db-art-star one">✧</span><span className="db-art-star two">✦</span></div></section>
        {error && <div className="db-notice" role="alert">{error} <button onClick={() => setRefresh(n => n + 1)}>Retry</button></div>}
        <section className="db-experiences" aria-label="Explore learning experiences"><div className="db-section-header"><div><span className="db-eyebrow">YOUR LEARNING MODES</span><h2>Choose your experience</h2></div><span className="db-subtle">Open a dedicated interactive workspace</span></div><div className="db-experience-grid"><Link className="db-experience db-exp-voice" to="/voice"><span className="db-exp-icon">◉</span><span className="db-exp-tag">SPEAK</span><h3>AI Voice Studio</h3><p>Practice out loud with microphone recognition, transcripts and spoken tutor replies.</p><strong>Enter voice studio ↗</strong></Link><Link className="db-experience db-exp-visual" to="/visual"><span className="db-exp-icon">◇</span><span className="db-exp-tag">EXPLORE</span><h3>Visual Lesson Studio</h3><p>Animate Dijkstra's algorithm, inspect graphs, solve quizzes and switch to light mode.</p><strong>Explore visual lessons ↗</strong></Link><Link className="db-experience db-exp-chat" to="/chat"><span className="db-exp-icon">▤</span><span className="db-exp-tag">CHAT</span><h3>AI Classroom</h3><p>Ask bilingual questions, review conversation history and continue saved sessions.</p><strong>Open advanced chat ↗</strong></Link></div></section><div className="db-section-header"><div><span className="db-eyebrow">AT A GLANCE</span><h2>Your learning pulse</h2></div><span className="db-subtle">Live data from your account</span></div>
        <div className="db-stats"><div className="db-stat"><span className="db-stat-icon cyan">▤</span><small>Learning sessions</small><strong>{sessions.length}</strong><span>Most recent 20 sessions</span></div><div className="db-stat"><span className="db-stat-icon violet">◇</span><small>Topics tracked</small><strong>{progress.length}</strong><span>Up to 100 topics</span></div><div className="db-stat"><span className="db-stat-icon pink">↗</span><small>Learning attempts</small><strong>{attempts}</strong><span>Recorded topic attempts</span></div><div className="db-stat"><span className="db-stat-icon mint">✦</span><small>Learning level</small><strong className="db-stat-word">{preferences.learning_level}</strong><span>{preferences.preferred_language} language</span></div></div>
        <div id="progress" className="db-analytics"><section className="db-card db-mastery"><div className="db-card-heading"><div><span className="db-eyebrow">LEARNING ANALYTICS</span><h2>Topic mastery</h2></div><span className="db-chip">REAL DATA</span></div><ProgressBars items={progress}/></section><section className="db-card db-overall"><div className="db-card-heading"><div><span className="db-eyebrow">YOUR PROGRESS</span><h2>Overall mastery</h2></div></div><Ring value={average}/><p>{progress.length ? "Average across assessed topics" : "Your mastery score will appear after submitted objective practice."}</p></section></div>
        <div className="db-lower"><section id="sessions" className="db-card db-sessions"><div className="db-card-heading"><div><span className="db-eyebrow">PICK UP WHERE YOU LEFT OFF</span><h2>Recent sessions</h2></div><span className="db-chip">{sessions.length} recent</span></div><label className="db-search">⌕ <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search your sessions" aria-label="Search sessions"/></label><div className="db-session-list">{filteredSessions.length ? filteredSessions.slice(0,6).map(session => <div className="db-session" key={session.id}><div className="db-session-icon">✧</div><div><strong>{session.topic}</strong><small>{session.language} · {dateLabel(session.created_at)}</small></div><Link className="db-session-tag" to={"/classroom?session=" + encodeURIComponent(session.id)}>Open ↗</Link></div>) : <p className="db-empty">{sessions.length ? "No sessions match your search." : "No learning sessions yet. Create your first one to get started."}</p>}</div></section><section id="start" className="db-card db-start"><span className="db-eyebrow">✦ YOUR NEXT STEP</span><h2>Start something new.</h2><p>Choose a topic and create a learning session. Open AI Classroom to chat with your tutor after creating a session.</p><form onSubmit={createSession}><label htmlFor="db-topic">What would you like to learn?</label><input id="db-topic" value={topic} onChange={event => setTopic(event.target.value)} maxLength={200} required placeholder="e.g. English greetings"/><button disabled={creating || !topic.trim()} type="submit">{creating ? "Creating…" : "Create learning session ↗"}</button></form>{notice && <p className="db-feedback" role="status">{notice}</p>}<div className="db-coming"><Link to="/voice">◉ Voice learning ↗</Link><Link to="/visual">◇ Visual lessons ↗</Link><Link to="/chat">▤ Advanced AI chat ↗</Link><Link to="/classroom">✦ AI classroom ↗</Link></div></section></div>
      </main>
    </div>
  </div>;
}
