import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getToken, request } from "./auth";
import { DeadlineCallAssistant } from "./DeadlineCallAssistant";
import { DeadlineLiveKitReminder } from "./DeadlineLiveKitReminder";
import "./assistant.css";

type Settings = { modes: string[]; timezone: string; preferred_language: string; reminder_phone: string | null; phone_verified: boolean; call_consent: boolean; reminder_lead_minutes: number[]; quiet_start: string | null; quiet_end: string | null; enabled_integrations: string[]; email_policy: string; notifications: Record<string, boolean>; retention_days: number; paused: boolean };
type Deadline = { id: string; title: string; due_at: string; timezone_name: string; priority: string; category: string; status: string; source: string };
type Draft = { id: string; thread_ref: string; recipient: string; subject: string; body: string; risk_category: string; status: string; approved_at: string | null };
type Integration = { provider: string; status: string; available: boolean; message: string; account_email: string | null };
type EmailItem = { id: string; sender: string; subject: string; snippet: string; category: string; needs_reply: boolean };
type CallItem = { id: string; status: string; destination_last_four: string; failure_code: string | null; created_at: string };
type LocalCallItem = { id: string; title: string; status: string; language: string; created_at: string; deadline_id: string | null };
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
  const [localCalls, setLocalCalls] = useState<LocalCallItem[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarItem[]>([]);
  const [pendingCommand, setPendingCommand] = useState<{ text: string; intent: string; preview: Record<string, string> } | null>(null);
  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [practiceCallTitle, setPracticeCallTitle] = useState("English speaking practice");
  const [practiceCallAt, setPracticeCallAt] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);
  const load = useCallback(async () => {
    try {
      const headers = auth();
      const [prefs, items, replies, providers, inbox, callLog, localCallLog, audit, calendar] = await Promise.all([
        request<Settings>("/assistant/settings", { headers }), request<Deadline[]>("/assistant/deadlines", { headers }),
        request<Draft[]>("/assistant/drafts", { headers }), request<Integration[]>("/assistant/integrations", { headers }),
        request<EmailItem[]>("/assistant/emails", { headers }).catch(() => []), request<CallItem[]>("/assistant/calls", { headers }).catch(() => []),
        request<LocalCallItem[]>("/assistant/local-calls", { headers }).catch(() => []),
        request<ActivityItem[]>("/assistant/activity", { headers }).catch(() => []),
        request<CalendarItem[]>("/assistant/calendar/events", { headers }).catch(() => []),
      ]);
      setSettings(prefs); setDeadlines(items); setDrafts(replies); setIntegrations(providers); setEmails(inbox); setCalls(callLog); setLocalCalls(localCallLog); setActivity(audit); setCalendarEvents(calendar); setError("");
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
  async function schedulePracticeCall(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!practiceCallTitle.trim() || !practiceCallAt || busy) return;
    const scheduledAt = new Date(practiceCallAt);
    if (!Number.isFinite(scheduledAt.getTime()) || scheduledAt.getTime() <= Date.now()) {
      setError("Choose a future date and time for this practice reminder."); return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      await request<Deadline>("/assistant/deadlines", { method: "POST", headers: auth(), body: JSON.stringify({
        title: practiceCallTitle.trim(), description: "Bilingual speaking practice reminder", due_at: scheduledAt.toISOString(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || settings?.timezone, priority: "normal", category: "practice_call",
      }) });
      setNotice("Practice reminder scheduled. You can start a browser voice session when it is due.");
      setPracticeCallAt(""); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not schedule the practice reminder."); }
    finally { setBusy(false); }
  }
  async function deadlineAction(id: string, action: "complete" | "cancel") { try { await request(`/assistant/deadlines/${id}/${action}`, { method: "POST", headers: auth() }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Could not update deadline."); } }
  async function editDeadline(item: Deadline) {
    const nextTitle = window.prompt("Edit deadline title", item.title);
    if (nextTitle === null || !nextTitle.trim()) return;
    const current = new Date(item.due_at); const local = new Date(current.getTime() - current.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    const nextDue = window.prompt("Edit due date/time (YYYY-MM-DDTHH:mm)", local);
    if (nextDue === null) return;
    try { await request(`/assistant/deadlines/${encodeURIComponent(item.id)}`, { method: "PATCH", headers: auth(), body: JSON.stringify({ title: nextTitle.trim(), due_at: new Date(nextDue).toISOString() }) }); setNotice("Deadline updated."); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update deadline."); }
  }
  async function deleteDeadline(id: string) {
    if (!window.confirm("Delete this deadline and its reminder history?")) return;
    try { await request(`/assistant/deadlines/${encodeURIComponent(id)}`, { method: "DELETE", headers: auth() }); setNotice("Deadline deleted."); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not delete deadline."); }
  }
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
  const practiceCalls = deadlines.filter(item => item.category === "practice_call" && ["upcoming", "overdue"].includes(item.status)).sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at));
  const nextPractice = practiceCalls[0];
  return <main className="as-shell as-scheduler-page">
    <header className="as-header"><Link to="/dashboard">← Dashboard</Link><span>BHASHA<strong>LEARN</strong> / PRACTICE CALLS</span><button onClick={signOut}>Sign out</button></header>
    <section className="as-scheduler-hero"><div className="as-scheduler-intro"><span className="as-scheduler-kicker">PRACTICE SPEAKING WITH YOUR AI TUTOR</span><h1>Schedule a Practice Call</h1><p>Build confidence with a short English or Telugu conversation practice.</p><a className="as-call-now" href="#browser-practice-call" onClick={() => { const controls = document.getElementById("browser-practice-call"); if (controls?.parentElement?.tagName === "DETAILS") (controls.parentElement as HTMLDetailsElement).open = true; }}>Call Now <span aria-hidden="true">→</span></a></div><div className="as-companion-card"><div className="as-companion-avatar" aria-hidden="true"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="57" fill="#eee9ff"/><path d="M22 105c4-24 16-36 38-36s34 12 38 36" fill="#7650e8"/><ellipse cx="60" cy="51" rx="25" ry="30" fill="#eebc98"/><path d="M34 50c-4-24 7-39 27-39 22 0 31 18 25 42-7-4-13-14-15-23-8 12-20 18-37 20" fill="#39245c"/><path d="M47 53h3m21 0h3" stroke="#49304f" strokeWidth="3" strokeLinecap="round"/><path d="M53 65q7 6 14 0" fill="none" stroke="#ad5971" strokeWidth="2" strokeLinecap="round"/><path d="M30 50a30 30 0 0 1 60 0" fill="none" stroke="#6a48d5" strokeWidth="7"/><rect x="26" y="47" width="9" height="24" rx="4" fill="#6a48d5"/><rect x="85" y="47" width="9" height="24" rx="4" fill="#6a48d5"/></svg></div><div><span className="as-companion-status"><i/> Ready for browser practice</span><h2>BhashaLearn AI Tutor</h2><p>Patient, bilingual speaking practice</p><span className="as-language-pills">English <b>·</b> తెలుగు</span><label className="as-pause as-pause-light"><input type="checkbox" checked={settings?.paused ?? true} onChange={e => void saveSettings({ paused: e.target.checked })} disabled={busy || !settings}/> Pause all automation</label></div></div></section>
    {error && <div className="as-error" role="alert">{error}<button onClick={() => void load()}>Retry</button></div>}{notice && <p className="as-notice" role="status">{notice}</p>}
    <section className="as-scheduler-grid">
      <article className="as-card as-schedule-card" id="schedule-practice-call"><div className="as-heading"><span>PLAN YOUR NEXT SESSION</span><h2>Schedule a practice call</h2></div><p className="as-muted">This creates a reminder in your account. It does not place an outbound phone call.</p><form className="as-schedule-form" onSubmit={schedulePracticeCall}><label className="as-field">Practice topic<input value={practiceCallTitle} onChange={e => setPracticeCallTitle(e.target.value)} required maxLength={200} placeholder="Everyday conversation practice"/></label><label className="as-field">Date and time<input type="datetime-local" value={practiceCallAt} min={new Date(Date.now() + 60_000).toISOString().slice(0,16)} onChange={e => setPracticeCallAt(e.target.value)} required/><small>{Intl.DateTimeFormat().resolvedOptions().timeZone || settings?.timezone}</small></label><button className="as-primary" disabled={busy || !settings || settings.paused}>{busy ? "Scheduling…" : "Schedule Practice Call"}</button></form>{settings?.paused && <p className="as-muted">Automation is paused. Resume it to schedule practice reminders.</p>}</article>
      <article className="as-card as-upcoming-card"><div className="as-heading"><span>YOUR NEXT SESSIONS</span><h2>Upcoming practice calls</h2></div>{nextPractice && <div className="as-next-call"><span className="as-next-icon" aria-hidden="true">◷</span><div><strong>{nextPractice.title}</strong><small>{new Date(nextPractice.due_at).toLocaleString()} · {nextPractice.timezone_name}</small></div><span className="as-upcoming-tag">{nextPractice.status}</span></div>}{practiceCalls.length > 1 && practiceCalls.slice(1).map(item => <div className="as-next-call as-more-call" key={item.id}><span className="as-next-icon" aria-hidden="true">◷</span><div><strong>{item.title}</strong><small>{new Date(item.due_at).toLocaleString()}</small></div><button type="button" onClick={() => void deadlineAction(item.id, "cancel")}>Cancel</button></div>)}{!practiceCalls.length && <p className="as-muted">No practice calls scheduled. Choose a topic and time to add a reminder.</p>}{nextPractice && <div className="as-next-actions"><button type="button" onClick={() => { const controls = document.getElementById("browser-practice-call"); if (controls?.parentElement?.tagName === "DETAILS") (controls.parentElement as HTMLDetailsElement).open = true; controls?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>Open call options</button><button type="button" onClick={() => void deadlineAction(nextPractice.id, "cancel")}>Cancel reminder</button></div>}</article>
    </section>
    <details className="as-settings-details as-call-controls"><summary>Open call controls and incoming-call options</summary><div id="browser-practice-call" className="as-call-feature"><DeadlineCallAssistant/><DeadlineLiveKitReminder deadlines={deadlines}/></div></details>
    <section className="as-card as-call-history"><div className="as-heading"><span>RECENT ACTIVITY</span><h2>Call History</h2></div>{localCalls.length === 0 && calls.length === 0 && <p className="as-muted">Your practice call history will appear here after a session.</p>}{[...localCalls.map(call => ({ id: call.id, title: call.title, status: call.status, created_at: call.created_at, label: "Browser practice" })), ...calls.map(call => ({ id: call.id, title: `•••• ${call.destination_last_four}`, status: call.status, created_at: call.created_at, label: "Phone reminder" }))].sort((a,b) => Date.parse(b.created_at)-Date.parse(a.created_at)).slice(0,8).map(call => <div className="as-history-row" key={call.id}><span className="as-history-icon" aria-hidden="true">☎</span><div><strong>{call.title}</strong><small>{call.label} · {new Date(call.created_at).toLocaleString()}</small></div><span className="as-history-status">{call.status}</span></div>)}</section>
    <details className="as-settings-details"><summary>Assistant, reminders, and account integrations</summary>
    {settings && <>
      <section className="as-grid">
        <article className="as-card"><div className="as-heading"><span>01 / PROFILE</span><h2>Assistant modes</h2></div><div className="as-checks">{(["student", "personal"] as const).map(mode => <label key={mode}><input type="checkbox" checked={settings.modes.includes(mode)} onChange={e => { const modes = e.target.checked ? [...settings.modes, mode] : settings.modes.filter(x => x !== mode); if (modes.length) void saveSettings({ modes }); }}/> {mode === "student" ? "Student" : "Personal"}</label>)}</div><label className="as-field">Timezone<input value={settings.timezone} maxLength={80} onChange={e => setSettings({ ...settings, timezone: e.target.value })} onBlur={() => void saveSettings({ timezone: settings.timezone })}/></label><label className="as-field">Reminder language<select value={settings.preferred_language} onChange={e => void saveSettings({ preferred_language: e.target.value })}><option value="en">English</option><option value="te">Telugu</option><option value="mixed">Telugu + English</option></select></label><label className="as-field">Reminder lead times (minutes)<input value={settings.reminder_lead_minutes.join(", ")} onChange={e => setSettings({ ...settings, reminder_lead_minutes: e.target.value.split(",").map(Number).filter(Number.isFinite) })} onBlur={() => void saveSettings({ reminder_lead_minutes: settings.reminder_lead_minutes })}/></label><div className="as-checks"><label><input type="checkbox" checked={settings.notifications.email} onChange={e => void saveSettings({ notifications: { email: e.target.checked } })}/> Email notifications</label><label><input type="checkbox" checked={settings.notifications.call} onChange={e => void saveSettings({ notifications: { call: e.target.checked } })}/> Call notifications</label></div><label className="as-field">Data retention (days)<input type="number" min={1} max={3650} value={settings.retention_days} onChange={e => setSettings({ ...settings, retention_days: Number(e.target.value) })} onBlur={() => void saveSettings({ retention_days: settings.retention_days })}/></label></article>
        <article className="as-card"><div className="as-heading"><span>02 / CALLS</span><h2>Phone reminders</h2></div><p className="as-state">{settings.phone_verified ? "Verified number" : "Phone number not verified"}</p><label className="as-field">Phone number (E.164)<input aria-label="Reminder phone number" placeholder="+15551234567" value={settings.reminder_phone || ""} onChange={e => setSettings({ ...settings, reminder_phone: e.target.value || null })} onBlur={() => void saveSettings({ reminder_phone: settings.reminder_phone })}/></label>{!settings.phone_verified ? <div className="as-actions"><button onClick={() => void startVerification()} disabled={!settings.reminder_phone}>Send verification SMS</button><label className="as-field">SMS code<input value={verifyCode} onChange={e => setVerifyCode(e.target.value)} inputMode="numeric" maxLength={10}/></label><button onClick={() => void confirmVerification()} disabled={!verifyCode}>Verify</button></div> : <label className="as-check"><input type="checkbox" checked={settings.call_consent} onChange={e => void saveSettings({ call_consent: e.target.checked })}/> I consent to deadline calls</label>}<p className="as-muted">Live calls require production mode, explicit switches, Twilio credentials, verified number, consent, and a running worker. Otherwise reminders are mock.</p><div className="as-row"><label className="as-field">Quiet hours start<input type="time" value={settings.quiet_start || ""} onChange={e => setSettings({ ...settings, quiet_start: e.target.value || null })} onBlur={() => void saveSettings({ quiet_start: settings.quiet_start, quiet_end: settings.quiet_end })}/></label><label className="as-field">Quiet hours end<input type="time" value={settings.quiet_end || ""} onChange={e => setSettings({ ...settings, quiet_end: e.target.value || null })} onBlur={() => void saveSettings({ quiet_start: settings.quiet_start, quiet_end: settings.quiet_end })}/></label></div></article>
      </section>
      <section className="as-grid">
        <article className="as-card"><div className="as-heading"><span>03 / DEADLINES</span><h2>Upcoming work</h2></div><form className="as-deadline-form" onSubmit={createDeadline}><label className="as-field">Title<input value={title} onChange={e => setTitle(e.target.value)} required maxLength={200} placeholder="Project submission"/></label><label className="as-field">Due date and time<input type="datetime-local" value={dueAt} onChange={e => setDueAt(e.target.value)} required/><small>Using {Intl.DateTimeFormat().resolvedOptions().timeZone || settings.timezone}</small></label><button className="as-primary" disabled={busy}>Add deadline</button></form><ul className="as-list">{deadlines.map(item => <li key={item.id}><div><strong>{item.title}</strong><small>{new Date(item.due_at).toLocaleString()} · {item.status} · {item.priority}</small></div><div className="as-actions">{item.status === "upcoming" && <><button onClick={() => void editDeadline(item)}>Edit</button><button onClick={() => void deadlineAction(item.id, "complete")}>Complete</button><button onClick={() => void deadlineAction(item.id, "cancel")}>Cancel</button></>}<button onClick={() => void deleteDeadline(item.id)}>Delete</button></div></li>)}</ul>{!deadlines.length && <p className="as-muted">No deadlines yet.</p>}</article>
        <article className="as-card"><div className="as-heading"><span>04 / INTEGRATIONS</span><h2>Connected accounts</h2></div>{integrations.map(item => <div className="as-provider" key={item.provider}><div><strong>{item.provider === "gmail" ? "Gmail inbox" : "Google Calendar"}</strong><small>{item.status} · {item.account_email || item.message}</small></div>{item.status === "connected" ? <button onClick={() => void disconnect(item.provider)}>Disconnect</button> : <button disabled={!item.available} onClick={() => void connect(item.provider)}>{item.available ? "Connect" : "Unavailable"}</button>}</div>)}{integrations.some(i => i.provider === "gmail" && i.status === "connected") && <button onClick={() => void syncGmail()}>Sync inbox</button>}<label className="as-field">Email policy<select value={settings.email_policy} onChange={e => void saveSettings({ email_policy: e.target.value })}><option value="draft_only">Draft only (default)</option><option value="disabled">Disabled</option></select></label><p className="as-muted">Each provider requires separate OAuth consent. Email sending requires individual approval; automatic replies are disabled.</p>{emails.map(email => <div className="as-provider" key={email.id}><div><strong>{email.subject || "(no subject)"}</strong><small>{email.sender} · {email.category} · {email.snippet}</small></div>{email.needs_reply && <button onClick={() => void makeDraft(email)}>Draft reply</button>}</div>)}</article>
      </section>
      <section className="as-grid">
        <article className="as-card"><div className="as-heading"><span>05 / APPROVAL</span><h2>Reply review</h2></div>{drafts.filter(d => !["rejected", "sent"].includes(d.status)).map(d => <div className="as-draft" key={d.id}><strong>{d.subject || "(no subject)"}</strong><small>To: {d.recipient} · {d.risk_category} · {d.status}</small><p>{d.body}</p>{d.status === "draft" && <div className="as-actions"><button onClick={async () => { const body = window.prompt("Edit reply", d.body); if (body !== null) { await request(`/assistant/drafts/${d.id}`, { method: "PATCH", headers: auth(), body: JSON.stringify({ body }) }); await load(); } }}>Edit</button><button onClick={() => void draftAction(d.id, "approve")}>Approve draft</button><button onClick={() => void draftAction(d.id, "reject")}>Reject</button></div>}{d.status === "approved" && <div className="as-actions"><p className="as-muted">Approved; send is a separate action.</p><button onClick={() => void sendDraft(d.id)} disabled={!integrations.some(i => i.provider === "gmail" && i.status === "connected")}>Send approved reply</button></div>}{["sending", "send_uncertain", "send_failed"].includes(d.status) && <p role="status">Send state: {d.status}. Check Gmail before recovery.</p>}</div>)}{!drafts.length && <p className="as-muted">No reply drafts.</p>}</article>
        <article className="as-card"><div className="as-heading"><span>06 / ACTIVITY</span><h2>Calls and automation</h2></div><p>Data retention: {settings.retention_days} days</p><h3>Recent activity</h3>{activity.slice(0, 12).map(a => <p key={a.id}>{new Date(a.created_at).toLocaleString()} · {a.action} · {a.outcome}</p>)}{!activity.length && <p className="as-muted">No activity recorded yet.</p>}</article>
      </section>
      <section className="as-card"><div className="as-heading"><span>07 / COMMANDS</span><h2>Ask your assistant</h2></div><form className="as-deadline-form" onSubmit={runCommand}><label className="as-field">Command in English or Telugu<input value={command} onChange={e => setCommand(e.target.value)} maxLength={2000} placeholder="Check my upcoming reminders"/></label><button className="as-primary">Run command</button></form>{pendingCommand && <div className="as-actions"><button onClick={() => setPendingCommand(null)}>Cancel request</button><button onClick={() => void confirmCommand()}>Confirm action</button></div>}<p className="as-muted">High-impact actions require confirmation. Gnani speech features require provider credentials.</p><h3>Calendar timeline</h3>{calendarEvents.map(item => <p key={item.id}>{new Date(item.starts_at).toLocaleString()} · {item.title}</p>)}{!calendarEvents.length && <p className="as-muted">No calendar events loaded. Connect Calendar to view authorized events.</p>}</section>
    </>}
    </details>
  </main>;
}
