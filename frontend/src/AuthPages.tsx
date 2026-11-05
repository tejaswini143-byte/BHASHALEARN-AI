import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, loginStudent, registerStudent, saveToken, type Student } from "./auth";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(Boolean(getToken()));
  const [authenticated, setAuthenticated] = useState(false);
  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) { setChecking(false); return; }
    getCurrentStudent(token).then(() => { if (active) setAuthenticated(true); })
      .catch(() => { clearToken(); })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (mode === "register" && !name.trim()) { setError("Please enter your name."); return; }
    if (mode === "register" && password.length < 12) { setError("Password must be at least 12 characters."); return; }
    setBusy(true);
    try {
      if (mode === "register") await registerStudent(email.trim(), name.trim(), password);
      const result = await loginStudent(email.trim(), password);
      saveToken(result.access_token);
      navigate("/dashboard", { replace: true });
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Something went wrong. Please try again.");
    } finally { setBusy(false); }
  }
  if (checking) return <main className="auth-screen"><p className="auth-wait">Checking your session…</p></main>;
  if (authenticated) return <Navigate to="/dashboard" replace />;
  return <main className="auth-screen">
    <div className="auth-glow auth-glow-one"/><div className="auth-glow auth-glow-two"/>
    <div className="auth-shell">
      <section className="auth-story">
        <Link to="/" className="auth-brand"><span className="brand-symbol">✦</span> BHASHA<span>LEARN</span> AI</Link>
        <span className="kicker">✦ YOUR LEARNING UNIVERSE</span>
        <h1>Every word is a <span className="gradient-text">new possibility.</span></h1>
        <p>Discover a learning space built for your voice, your language, and your pace.</p>
        <div className="auth-story-card"><span>✧</span><div><strong>తెలుగు + English</strong><small>One journey. Endless discoveries.</small></div></div>
        <div className="auth-story-footer">VOICE · VISUALS · AI CONVERSATION</div>
      </section>
      <section className="auth-card glass" aria-label={mode === "login" ? "Sign in" : "Create account"}>
        <div className="auth-card-icon">✦</div>
        <span className="auth-eyebrow">{mode === "login" ? "WELCOME BACK" : "START YOUR JOURNEY"}</span>
        <h2>{mode === "login" ? "Good to see you again." : "Create your account."}</h2>
        <p>{mode === "login" ? "Sign in to continue learning your way." : "Your personal AI classroom is waiting."}</p>
        <form onSubmit={submit}>
          {mode === "register" && <label className="auth-field">Your name<input autoComplete="name" required maxLength={120} value={name} onChange={event => setName(event.target.value)} placeholder="What should we call you?"/></label>}
          <label className="auth-field">Email address<input type="email" autoComplete="email" required maxLength={320} value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com"/></label>
          <label className="auth-field">Password<div className="password-wrap"><input type={visible ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "register" ? 12 : undefined} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} placeholder={mode === "register" ? "At least 12 characters" : "Enter your password"}/><button type="button" className="password-toggle" aria-label={visible ? "Hide password" : "Show password"} onClick={() => setVisible(!visible)}>{visible ? "Hide" : "Show"}</button></div></label>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button type="submit" className="auth-submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in →" : "Create account →"}</button>
        </form>
        <p className="auth-switch">{mode === "login" ? "New to BHASHALEARN?" : "Already have an account?"} <Link to={mode === "login" ? "/register" : "/login"}>{mode === "login" ? "Create an account" : "Sign in"}</Link></p>
        <Link to="/" className="auth-back">← Back to home</Link>
      </section>
    </div>
  </main>;
}

export function ProtectedDashboard() {
  const navigate = useNavigate();
  const [student, setStudent] = useState<Student | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) { navigate("/login", { replace: true }); return; }
    getCurrentStudent(token).then(value => { if (active) setStudent(value); })
      .catch(() => { clearToken(); if (active) navigate("/login", { replace: true }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [navigate]);
  if (loading) return <main className="auth-screen"><p className="auth-wait">Loading your learning space…</p></main>;
  if (!student) return null;
  return <main className="dashboard-placeholder"><div className="dashboard-top"><Link to="/" className="auth-brand"><span className="brand-symbol">✦</span> BHASHA<span>LEARN</span> AI</Link><button onClick={() => { clearToken(); navigate("/login", { replace: true }); }}>Sign out ↗</button></div><section className="dashboard-welcome glass"><span className="kicker">✦ YOU'RE SIGNED IN</span><h1>Welcome, <span className="gradient-text">{student.display_name}!</span></h1><p>Your account is connected to BHASHALEARN AI. The interactive dashboard is coming in FE-04.</p><div className="dashboard-email">✓ Signed in as {student.email}</div></section></main>;
}
