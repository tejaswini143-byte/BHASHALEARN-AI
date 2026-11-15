import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, loginStudent, registerStudent, saveToken } from "./auth";

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
        {mode === "login" && <Link className="auth-forgot" to="/forgot-password">Forgot password?</Link>}
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

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage(""); setError("");
    try {
      const response = await fetch("/api/v1/auth/password-reset/request", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: email.trim() }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof result?.detail === "string" ? result.detail : "Password recovery is unavailable.");
      setMessage(typeof result?.message === "string" ? result.message : "If an account exists for that address, a reset link will be sent.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not request a reset link."); }
    finally { setBusy(false); }
  }
  return <AuthFrame label="Reset your password" eyebrow="ACCOUNT RECOVERY" title="Reset your password" description="Enter your account email and we’ll send a one-use reset link if it is registered.">
    <form onSubmit={submit}><label className="auth-field">Email address<input type="email" autoComplete="email" required maxLength={320} value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com"/></label>
      {error && <div className="auth-error" role="alert">{error}</div>}{message && <div className="auth-success" role="status">{message}</div>}
      <button type="submit" className="auth-submit" disabled={busy}>{busy ? "Sending…" : "Send reset link →"}</button>
    </form><Link to="/login" className="auth-back">← Back to login</Link>
  </AuthFrame>;
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(token ? "" : "This reset link is missing its token. Request a new one.");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage("");
    if (password !== confirm) { setError("Passwords do not match."); return; }
    setBusy(true);
    try {
      const response = await fetch("/api/v1/auth/password-reset/complete", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, password }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof result?.detail === "string" ? result.detail : "This reset link is invalid or expired.");
      setMessage(typeof result?.message === "string" ? result.message : "Your password has been updated.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not reset your password."); }
    finally { setBusy(false); }
  }
  return <AuthFrame label="Choose a new password" eyebrow="SECURE YOUR ACCOUNT" title="Choose a new password" description="Reset links expire after 30 minutes and work once.">
    <form onSubmit={submit}><label className="auth-field">New password<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} placeholder="At least 12 characters"/></label>
      <label className="auth-field">Confirm new password<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirm} onChange={event => setConfirm(event.target.value)} placeholder="Enter it again"/></label>
      {error && <div className="auth-error" role="alert">{error}</div>}{message && <div className="auth-success" role="status">{message} <Link to="/login">Sign in</Link></div>}
      <button type="submit" className="auth-submit" disabled={busy || !token || Boolean(message)}>{busy ? "Updating…" : "Update password →"}</button>
    </form><Link to="/forgot-password" className="auth-back">Request another reset link</Link>
  </AuthFrame>;
}

function AuthFrame({ label, eyebrow, title, description, children }: { label: string; eyebrow: string; title: string; description: string; children: React.ReactNode }) {
  return <main className="auth-screen"><div className="auth-glow auth-glow-one"/><div className="auth-glow auth-glow-two"/><div className="auth-shell">
    <section className="auth-story"><Link to="/" className="auth-brand"><span className="brand-symbol">✦</span> BHASHA<span>LEARN</span> AI</Link><span className="kicker">✦ LEARN LANGUAGES. BUILD YOUR FUTURE.</span><h1>Every word is a <span className="gradient-text">new possibility.</span></h1><p>Securely return to your learning journey.</p><div className="auth-story-card"><span>✧</span><div><strong>తెలుగు + English</strong><small>One journey. Endless discoveries.</small></div></div><div className="auth-story-footer">LEARN · PRACTICE · GROW</div></section>
    <section className="auth-card glass" aria-label={label}><div className="auth-card-icon">✉</div><span className="auth-eyebrow">{eyebrow}</span><h2>{title}</h2><p>{description}</p>{children}</section>
  </div></main>;
}

export { ProtectedDashboard } from "./Dashboard";
