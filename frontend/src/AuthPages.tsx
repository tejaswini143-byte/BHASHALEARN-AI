import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, loginStudent, registerStudent, saveToken } from "./auth";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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
    if (mode === "register" && password !== confirmPassword) { setError("Passwords do not match."); return; }
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
    <div className="auth-shell">
      <section className="auth-story">
        <Link to="/" className="auth-brand"><span className="brand-symbol">▣</span><span>BHASHALEARN <small>AI</small></span></Link>
        <div className="auth-story-copy">
          <span className="auth-eyebrow">LEARN · PRACTICE · GROW</span>
          <h1>Learn Languages.<br/>Build Your Future.</h1>
          <p>AI-powered bilingual learning assistant for Telugu &amp; English.</p>
        </div>
        <AuthStudentIllustration />
        <span className="auth-story-footer">Learn&nbsp; · &nbsp;Practice&nbsp; · &nbsp;Grow</span>
      </section>
      <section className="auth-card" aria-label={mode === "login" ? "Sign in" : "Create account"}>
        <span className="auth-eyebrow">{mode === "login" ? "WELCOME BACK 👋" : "CREATE YOUR ACCOUNT"}</span>
        <h2>{mode === "login" ? "Welcome Back" : "Create Account"}</h2>
        <p>{mode === "login" ? "Sign in to your account" : "Join BHASHALEARN AI and start learning."}</p>
        <form onSubmit={submit}>
          {mode === "register" && <label className="auth-field">Your name<input autoComplete="name" required maxLength={120} value={name} onChange={event => setName(event.target.value)} placeholder="What should we call you?"/></label>}
          <label className="auth-field">Email address<input type="email" autoComplete="email" required maxLength={320} value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com"/></label>
          {mode === "login" && <Link className="auth-forgot" to="/forgot-password">Forgot password?</Link>}
          <label className="auth-field">Password<div className="password-wrap"><input type={visible ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "register" ? 12 : undefined} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} placeholder={mode === "register" ? "At least 12 characters" : "Enter your password"}/><button type="button" className="password-toggle" aria-label={visible ? "Hide password" : "Show password"} onClick={() => setVisible(!visible)}>{visible ? "Hide" : "Show"}</button></div></label>
          {mode === "register" && <label className="auth-field">Confirm password<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} placeholder="Enter your password again"/></label>}
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button type="submit" className="auth-submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in →" : "Create account →"}</button>
        </form>
        <div className="auth-divider"><span>or continue with</span></div>
        <p className="auth-switch">{mode === "login" ? "Don’t have an account?" : "Already have an account?"} <Link to={mode === "login" ? "/register" : "/login"}>{mode === "login" ? "Register" : "Sign in"}</Link></p>
        <Link to="/" className="auth-back">← Back to home</Link>
      </section>
    </div>
  </main>;
}

function AuthStudentIllustration() {
  return <div className="auth-student-scene" aria-label="A student learning Telugu and English">
    <span className="auth-speech auth-speech-left">నమస్తే!</span><span className="auth-speech auth-speech-right">Hello!</span>
    <svg viewBox="0 0 420 330" role="img" aria-label="Illustration of a student with a book">
      <defs><linearGradient id="authBook" x1="0" x2="1"><stop stopColor="#fff"/><stop offset="1" stopColor="#e9e2ff"/></linearGradient><linearGradient id="authCloth" x1="0" x2="1"><stop stopColor="#7c3ce4"/><stop offset="1" stopColor="#c44cbb"/></linearGradient></defs>
      <path d="M0 278h420v52H0z" fill="#49359c" opacity=".5"/><path d="M15 278v-83h34v83m14 0v-118h34v118m16 0v-68h33v68" fill="#bba8ff" opacity=".28"/>
      <path d="M310 278v-67h28v67m11 0v-97h28v97m9 0v-52h22v52" fill="#bba8ff" opacity=".25"/>
      <ellipse cx="209" cy="153" rx="66" ry="79" fill="#291754"/><path d="M155 148c0-52 23-82 59-82 40 0 61 31 58 79-2 32-11 57-24 72l-10-18-77-3c-9-12-6-30-6-48" fill="#251344"/>
      <ellipse cx="213" cy="151" rx="45" ry="56" fill="#f4bf9c"/><path d="M166 144c-8-42 14-81 48-81 41 0 64 31 62 72-19-6-28-18-35-31-17 21-44 34-75 40" fill="#271348"/>
      <path d="M190 150h5m35 0h5" stroke="#492755" strokeWidth="4" strokeLinecap="round"/><path d="M207 171q8 7 17 0" fill="none" stroke="#ad5475" strokeWidth="3" strokeLinecap="round"/>
      <path d="M138 300c6-70 31-102 75-102s75 31 81 102" fill="url(#authCloth)"/><path d="M179 216l34 54 34-54" fill="#f3dbff" opacity=".8"/>
      <path d="M146 265l59 27v-62l-59-25z" fill="url(#authBook)"/><path d="M205 230l65-25v62l-65 25z" fill="#fff"/><path d="M156 239l38 17m-38-5l38 17m22-19l45-17m-45 30l45-17" stroke="#a493dd" strokeWidth="3" opacity=".75"/>
      <path d="M177 124q12-8 24 0m27 0q12-8 24 0" fill="none" stroke="#271348" strokeWidth="4" strokeLinecap="round"/>
    </svg>
  </div>;
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
    <section className="auth-story"><Link to="/" className="auth-brand"><span className="brand-symbol">▣</span><span>BHASHALEARN <small>AI</small></span></Link><div className="auth-story-copy"><span className="auth-eyebrow">{eyebrow}</span><h1>Learn Languages.<br/>Build Your Future.</h1><p>AI-powered bilingual learning assistant for Telugu &amp; English.</p></div><AuthStudentIllustration/><span className="auth-story-footer">Learn&nbsp; · &nbsp;Practice&nbsp; · &nbsp;Grow</span></section>
    <section className="auth-card" aria-label={label}><span className="auth-eyebrow">{eyebrow}</span><h2>{title}</h2><p>{description}</p>{children}</section>
  </div></main>;
}

export { ProtectedDashboard } from "./Dashboard";
