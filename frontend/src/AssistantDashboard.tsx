import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getToken, request } from "./auth";
import "./assistant.css";

type Settings = { modes: string[]; timezone: string; preferred_language: string; reminder_phone: string | null; phone_verified: boolean; call_consent: boolean; reminder_lead_minutes: number[]; quiet_start: string | null; quiet_end: string | null; enabled_integrations: string[]; email_policy: string; notifications: Record<string, boolean>; retention_days: number; paused: boolean };
type Deadline = { id: string; title: string; due_at: string; timezone_name: string; priority: string; category: string; status: string; source: string };
type Draft = { id: string; thread_ref: string; recipient: string; subject: string; body: string; risk_category: string; status: string; approved_at: string | null };
type Integration = { provider: string; status: string; available: boolean; message: string; account_email: string | null };
type EmailItem = { id: string; sender: string; subject: string; snippet: string; category: string; needs_reply: boolean };
type CallItem = { id: string; status: string; destination_last_four: string; failure_code: string | null; created_at: string };
type ActivityItem = { id: string; action: string; outcome: string; created_at: string };
type CalendarItem = { id: string; title: string; starts_at: string; ends_at: string; timezone: string };
const auth = (): Record<string, string> => { const token = getToken(); return token ? { Authorization: `Bearer ${token}` } : {}; };

export function AssistantDashboard() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [deadlines, setDeadlines] = useState<Deadline[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [calls, setCalls] = useState<CallItem[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarItem[]>([]);
  const [pendingCommand, setPendingCommand] = useState<{ text: string; intent: string; preview: Record<string, string> } | null>(null);
  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);
  const load = useCallback(async () => {
    try {
      const headers = auth();
      const [prefs, items, replies, providers, inbox, callLog, audit, calendar] = await Promise.all([
        request<Settings>("/assistant/settings", { headers }), request<Deadline[]>("/assistant/deadlines", { headers }),
        request<Draft[]>("/assistant/drafts", { headers }), request<Integration[]>("/assistant/integrations", { headers }),
        request<EmailItem[]>("/assistant/emails", { headers }).catch(() => []), request<CallItem[]>("/assistant/calls", { headers }).catch(() => []),
        request<ActivityItem[]>("/assistant/activity", { headers }).catch(() => []),
        request<CalendarItem[]>("/assistant/calendar/events", { headers }).catch(() => []),
      ]);
      setSettings(prefs); setDeadlines(items); setDrafts(replies); setIntegrations(providers); setEmails(inbox); setCalls(callLog); setActivity(audit); setCalendarEvents(calendar); setError("");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
      setError(cause instanceof Error ? cause.message : "Could not load assistant settings.");
    }
  }, [signOut]);
  useEffect(() => { void load(); }, [load]);
  async function saveSettings(changes: Partial<Settings>) {
    if (!settings) return;
    setBusy(true); setNotice("");
    try { const saved = await request<Settings>("/assistant/settings", { method: "PATCH", headers: auth(), body: JSON.stringify(changes) }); setSettings(saved); setNotice("Assistant settings saved."); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save settings."); }
    finally { setBusy(false); }
  }
  async function createDeadline(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!title.trim() || !dueAt || busy) return;
    setBusy(true);
    try { await request<Deadline>("/assistant/deadlines", { method: "POST", headers: auth(), body: JSON.stringify({ title: title.trim(), due_at: new Date(dueAt).toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || settings?.timezone }) }); setTitle(""); setDueAt(""); setNotice("Deadline saved; reminders were scheduled."); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save deadline."); } finally { setBusy(false); }
  }
  async function deadlineAction(id: string, action: "complete" | "cancel") { try { await request(`/assistant/deadlines/${id}/${action}`, { method: "POST", headers: auth() }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Could not update deadline."); } }
  async function connect(provider: string) { try { const result = await request<{ authorization_url: string }>(`/assistant/integrations/${provider}/connect`, { method: "POST", headers: auth() }); window.location.assign(result.authorization_url); } catch (e) { setError(e instanceof Error ? e.message : "Integration unavailable."); } }
  async function disconnect(provider: string) { if (!window.confirm(`Disconnect ${provider}?`)) return; try { await request(`/assistant/integrations/${provider}`, { method: "DELETE", headers: auth() }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Disconnect failed."); } }
  async function startVerification() {
    if (!settings?.reminder_phone || !window.confirm("Send a verification SMS to this number?")) return;
    try { await request("/assistant/phone/verification/start", { method: "POST", headers: auth(), body: JSON.stringify({ phone: settings.reminder_phone, consent_to_verification_sms: true }) }); setNotice("Verification SMS requested."); }
    catch (e) { setError(e instanceof Error ? e.message : "Phone verification unavailable."); }
  }
  async function confirmVerification() { try { await request("/assistant/phone/verification/confirm", { method: "POST", headers: auth(), body: JSON.stringify({ code: verifyCode }) }); setVerifyCode(""); await load(); setNotice("Phone verified. Call consent remains off until enabled."); } catch (e) { setError(e instanceof Error ? e.message : "Phone verification failed."); } }
  async function syncGmail() { try { await request("/assistant/integrations/gmail/sync", { method: "POST", headers: auth() }); await load(); setNotice("Inbox synchronization completed."); } catch (e) { setError(e instanceof Error ? e.message : "Inbox sync failed."); } }
  async function makeDraft(email: EmailItem) {
    const points = window.prompt("What would you like to say? Include only facts you want in the reply."); if (!points?.trim()) return;
    const tone = window.prompt("Tone: formal, professional, or casual", "professional") || "professional";
    const language = window.prompt("Language: en, te, or mixed", settings?.preferred_language || "en") || "en";
    try { await request(`/assistant/emails/${email.id}/draft`, { method: "POST", headers: auth(), body: JSON.stringify({ response_points: points.trim(), tone, language }) }); await load(); setNotice("Reply draft created; it has not been sent."); } catch (e) { setError(e instanceof Error ? e.message : "Draft generation failed."); }
  }
  async function draftAction(id: string, action: "approve" | "reject") { try { await request(`/assistant/drafts/${id}/${action}`, { method: "POST", headers: auth() }); await load(); setNotice(action === "approve" ? "Approved. Sending remains a separate action." : "Draft rejected."); } catch (e) { setError(e instanceof Error ? e.message : "Draft update failed."); } }
  async function sendDraft(id: string) {
    if (!window.confirm("Send this approved email now?")) return;
    try { await request(`/assistant/drafts/${id}/send`, { method: "POST", headers: { ...auth(), "Idempotency-Key": crypto.randomUUID() } }); await load(); setNotice("Gmail confirmed the message was sent."); }
    catch (e) { setError(e instanceof Error ? e.message : "Send outcome could not be confirmed. Check Gmail before retrying."); await load(); }
  }
  async function runCommand(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!command.trim()) return; try { const result = await request<{ intent: string; requires_confirmation?: boolean; preview?: Record<string, string>; message?: string; items?: unknown[] }>("/assistant/voice/commands", { method: "POST", headers: auth(), body: JSON.stringify({ text: command.trim(), confirmed: false }) }); if (result.requires_confirmation && result.preview) { setPendingCommand({ text: command.trim(), intent: result.intent, preview: result.preview }); setNotice(`Review before confirming: ${JSON.stringify(result.preview)}`); } else { setPendingCommand(null); setNotice(result.message || (result.items ? `${result.items.length} item(s) found.` : "Command completed.")); await load(); } } catch (e) { setError(e instanceof Error ? e.message : "Assistant command failed."); } }
  async function confirmCommand() { if (!pendingCommand) return; const { intent, preview, text } = pendingCommand; const payload: Record<string, unknown> = { text, confirmed: true }; if (intent === "create_deadline") { payload.title = preview.title; payload.due_at = preview.due_at; } if (intent === "calendar_event") { payload.title = preview.title; payload.starts_at = preview.starts_at; payload.ends_at = preview.ends_at; } try { await request("/assistant/voice/commands", { method: "POST", headers: auth(), body: JSON.stringify(payload) }); setPendingCommand(null); setNotice("Confirmed action completed."); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Action could not be completed."); } }
  if (!settings && !error) return <main className="as-shell" role="status">Loading your assistant…</main>;
  return <main className="as-shell">
    <header className="as-header"><Link to="/dashboard">← Dashboard</Link><span>BHASHA<strong>LEARN</strong> / AI ASSISTANT</span><button onClick={signOut}>Sign out</button></header>
    <section className="as-hero"><div><span>PRIVATE PRODUCTIVITY SPACE</span><h1>Your personal assistant</h1><p>Deadlines, reminders and email review in one place, isolated to your account.</p></div><label className="as-pause"><input type="checkbox" checked={settings?.paused ?? true} onChange={e => void saveSettings({ paused: e.target.checked })} disabled={busy || !settings}/> Pause all automation</label></section>
    {error && <div className="as-error" role="alert">{error}<button onClick={() => void load()}>Retry</button></div>}{notice && <p className="as-notice" role="status">{notice}</p>}
    {settings && <>
      <section className="as-grid">
        <article className="as-card"><div className="as-heading"><span>01 / PROFILE</span><h2>Assistant modes</h2></div><div className="as-checks">{(["student", "personal"] as const).map(mode => <label key={mode}><input type="checkbox" checked={settings.modes.includes(mode)} onChange={e => { const modes = e.target.checked ? [...settings.modes, mode] : settings.modes.filter(x => x !== mode); if (modes.length) void saveSettings({ modes }); }}/> {mode === "student" ? "Student" : "Personal"}</label>)}</div><label className="as-field">Timezone<input value={settings.timezone} maxLength={80} onChange={e => setSettings({ ...settings, timezone: e.target.value })} onBlur={() => void saveSettings({ timezone: settings.timezone })}/></label><label className="as-field">Reminder language<select value={settings.preferred_language} onChange={e => void saveSettings({ preferred_language: e.target.value })}><option value="en">English</option><option value="te">Telugu</option><option value="mixed">Telugu + English</option></select></label><label className="as-field">Reminder lead times (minutes)<input value={settings.reminder_lead_minutes.join(", ")} onChange={e => setSettings({ ...settings, reminder_lead_minutes: e.target.value.split(",").map(Number).filter(Number.isFinite) })} onBlur={() => void saveSettings({ reminder_lead_minutes: settings.reminder_lead_minutes })}/></label><div className="as-checks"><label><input type="checkbox" checked={settings.notifications.email} onChange={e => void saveSettings({ notifications: { email: e.target.checked } })}/> Email notifications</label><label><input type="checkbox" checked={settings.notifications.call} onChange={e => void saveSettings({ notifications: { call: e.target.checked } })}/> Call notifications</label></div><label className="as-field">Data retention (days)<input type="number" min={1} max={3650} value={settings.retention_days} onChange={e => setSettings({ ...settings, retention_days: Number(e.target.value) })} onBlur={() => void saveSettings({ retention_days: settings.retention_days })}/></label></article>
        <article className="as-card"><div className="as-heading"><span>02 / CALLS</span><h2>Phone reminders</h2></div><p className="as-state">{settings.phone_verified ? "Verified number" : "Phone number not verified"}</p><label className="as-field">Phone number (E.164)<input aria-label="Reminder phone number" placeholder="+15551234567" value={settings.reminder_phone || ""} onChange={e => setSettings({ ...settings, reminder_phone: e.target.value || null })} onBlur={() => void saveSettings({ reminder_phone: settings.reminder_phone })}/></label>{!settings.phone_verified ? <div className="as-actions"><button onClick={() => void startVerification()} disabled={!settings.reminder_phone}>Send verification SMS</button><label className="as-field">SMS code<input value={verifyCode} onChange={e => setVerifyCode(e.target.value)} inputMode="numeric" maxLength={10}/></label><button onClick={() => void confirmVerification()} disabled={!verifyCode}>Verify</button></div> : <label className="as-check"><input type="checkbox" checked={settings.call_consent} onChange={e => void saveSettings({ call_consent: e.target.checked })}/> I consent to deadline calls</label>}<p className="as-muted">Live calls require production mode, explicit switches, Twilio credentials, verified number, consent, and a running worker. Otherwise reminders are mock.</p><div className="as-row"><label className="as-field">Quiet hours start<input type="time" value={settings.quiet_start || ""} onChange={e => setSettings({ ...settings, quiet_start: e.target.value || null })} onBlur={() => void saveSettings({ quiet_start: settings.quiet_start, quiet_end: settings.quiet_end })}/></label><label className="as-field">Quiet hours end<input type="time" value={settings.quiet_end || ""} onChange={e => setSettings({ ...settings, quiet_end: e.target.value || null })} onBlur={() => void saveSettings({ quiet_start: settings.quiet_start, quiet_end: settings.quiet_end })}/></label></div></article>
      </section>
      <section className="as-grid">
        <article className="as-card"><div className="as-heading"><span>03 / DEADLINES</span><h2>Upcoming work</h2></div><form className="as-deadline-form" onSubmit={createDeadline}><label className="as-field">Title<input value={title} onChange={e => setTitle(e.target.value)} required maxLength={200} placeholder="Project submission"/></label><label className="as-field">Due date and time<input type="datetime-local" value={dueAt} onChange={e => setDueAt(e.target.value)} required/><small>Using {Intl.DateTimeFormat().resolvedOptions().timeZone || settings.timezone}</small></label><button className="as-primary" disabled={busy}>Add deadline</button></form><ul className="as-list">{deadlines.map(item => <li key={item.id}><div><strong>{item.title}</strong><small>{new Date(item.due_at).toLocaleString()} · {item.status} · {item.priority}</small></div>{item.status === "upcoming" && <div className="as-actions"><button onClick={() => void deadlineAction(item.id, "complete")}>Complete</button><button onClick={() => void deadlineAction(item.id, "cancel")}>Cancel</button></div>}</li>)}</ul>{!deadlines.length && <p className="as-muted">No deadlines yet.</p>}</article>
        <article className="as-card"><div className="as-heading"><span>04 / INTEGRATIONS</span><h2>Connected accounts</h2></div>{integrations.map(item => <div className="as-provider" key={item.provider}><div><strong>{item.provider === "gmail" ? "Gmail inbox" : "Google Calendar"}</strong><small>{item.status} · {item.account_email || item.message}</small></div>{item.status === "connected" ? <button onClick={() => void disconnect(item.provider)}>Disconnect</button> : <button disabled={!item.available} onClick={() => void connect(item.provider)}>{item.available ? "Connect" : "Unavailable"}</button>}</div>)}{integrations.some(i => i.provider === "gmail" && i.status === "connected") && <button onClick={() => void syncGmail()}>Sync inbox</button>}<label className="as-field">Email policy<select value={settings.email_policy} onChange={e => void saveSettings({ email_policy: e.target.value })}><option value="draft_only">Draft only (default)</option><option value="disabled">Disabled</option></select></label><p className="as-muted">Each provider requires separate OAuth consent. Email sending requires individual approval; automatic replies are disabled.</p>{emails.map(email => <div className="as-provider" key={email.id}><div><strong>{email.subject || "(no subject)"}</strong><small>{email.sender} · {email.category} · {email.snippet}</small></div>{email.needs_reply && <button onClick={() => void makeDraft(email)}>Draft reply</button>}</div>)}</article>
      </section>
      <section className="as-grid">
        <article className="as-card"><div className="as-heading"><span>05 / APPROVAL</span><h2>Reply review</h2></div>{drafts.filter(d => !["rejected", "sent"].includes(d.status)).map(d => <div className="as-draft" key={d.id}><strong>{d.subject || "(no subject)"}</strong><small>To: {d.recipient} · {d.risk_category} · {d.status}</small><p>{d.body}</p>{d.status === "draft" && <div className="as-actions"><button onClick={async () => { const body = window.prompt("Edit reply", d.body); if (body !== null) { await request(`/assistant/drafts/${d.id}`, { method: "PATCH", headers: auth(), body: JSON.stringify({ body }) }); await load(); } }}>Edit</button><button onClick={() => void draftAction(d.id, "approve")}>Approve draft</button><button onClick={() => void draftAction(d.id, "reject")}>Reject</button></div>}{d.status === "approved" && <div className="as-actions"><p className="as-muted">Approved; send is a separate action.</p><button onClick={() => void sendDraft(d.id)} disabled={!integrations.some(i => i.provider === "gmail" && i.status === "connected")}>Send approved reply</button></div>}{["sending", "send_uncertain", "send_failed"].includes(d.status) && <p role="status">Send state: {d.status}. Check Gmail before recovery.</p>}</div>)}{!drafts.length && <p className="as-muted">No reply drafts.</p>}</article>
        <article className="as-card"><div className="as-heading"><span>06 / ACTIVITY</span><h2>Calls and automation</h2></div><p>Data retention: {settings.retention_days} days</p><h3>Call history</h3>{calls.map(c => <p key={c.id}>{new Date(c.created_at).toLocaleString()} · •••• {c.destination_last_four} · {c.status}{c.failure_code ? ` · ${c.failure_code}` : ""}</p>)}{!calls.length && <p className="as-muted">No call attempts recorded.</p>}<h3>Recent activity</h3>{activity.slice(0, 12).map(a => <p key={a.id}>{new Date(a.created_at).toLocaleString()} · {a.action} · {a.outcome}</p>)}{!activity.length && <p className="as-muted">No activity recorded yet.</p>}</article>
      </section>
      <section className="as-card"><div className="as-heading"><span>07 / COMMANDS</span><h2>Ask your assistant</h2></div><form className="as-deadline-form" onSubmit={runCommand}><label className="as-field">Command in English or Telugu<input value={command} onChange={e => setCommand(e.target.value)} maxLength={2000} placeholder="Check my upcoming reminders"/></label><button className="as-primary">Run command</button></form>{pendingCommand && <div className="as-actions"><button onClick={() => setPendingCommand(null)}>Cancel request</button><button onClick={() => void confirmCommand()}>Confirm action</button></div>}<p className="as-muted">High-impact actions require confirmation. Gnani speech features require provider credentials.</p><h3>Calendar timeline</h3>{calendarEvents.map(item => <p key={item.id}>{new Date(item.starts_at).toLocaleString()} · {item.title}</p>)}{!calendarEvents.length && <p className="as-muted">No calendar events loaded. Connect Calendar to view authorized events.</p>}</section>
    </>}
  </main>;
}
