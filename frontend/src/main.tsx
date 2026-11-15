import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { LiveKitReminder } from './LiveKitReminder';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001/api';
type Deadline = { id: string; title: string; kind: string; delivery_mode: 'browser'|'call'; due_at: string; timezone: string; reminder_minutes_before: number; completed_at?: string | null };
type Reminder = { id: string; deadline_id: string; scheduled_at: string; status: string };
type VoiceSessionHistory = { id: string; reminder_id: string | null; status: string; language: string; created_at: string; ended_at?: string | null };
type CallHistory = { id: string; reminder_id: string; status: string; created_at: string; ended_at?: string | null; failure?: string | null };

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem('accessToken') || '');
  const [deadlines, setDeadlines] = useState<Deadline[]>([]), [reminders, setReminders] = useState<Reminder[]>([]);
  const [voiceSessions, setVoiceSessions] = useState<VoiceSessionHistory[]>([]);
  const [calls, setCalls] = useState<CallHistory[]>([]);
  const [title, setTitle] = useState(''), [kind, setKind] = useState('assignment'), [deliveryMode, setDeliveryMode] = useState<'browser'|'call'>('browser'), [due, setDue] = useState('');
  const [reminderMinutes, setReminderMinutes] = useState(1440);
  const [message, setMessage] = useState(''); const [tab, setTab] = useState('upcoming');
  const [transcript, setTranscript] = useState(''), [reply, setReply] = useState('');
  const [language, setLanguage] = useState('te-IN'), [consent, setConsent] = useState(false), [remindersEnabled, setRemindersEnabled] = useState(true), [callStatus, setCallStatus] = useState<string[]>([]);
  const [authMode, setAuthMode] = useState<'login'|'register'>('login'), [authEmail, setAuthEmail] = useState(''), [authPassword, setAuthPassword] = useState(''), [authError, setAuthError] = useState('');
  const spokenReminders = useRef(new Set<string>());
  const auth = { Authorization: `Bearer ${token}` };
  async function load(accessToken = token) {
    if (!accessToken) return;
    const headers = { Authorization: `Bearer ${accessToken}` };
    const [d, r, v, c] = await Promise.all([fetch(`${API}/deadlines`, { headers }), fetch(`${API}/reminders`, { headers }), fetch(`${API}/voice/sessions`, { headers }), fetch(`${API}/calls`, { headers })]);
    if (d.ok) setDeadlines(await d.json()); if (r.ok) setReminders(await r.json()); if (v.ok) setVoiceSessions(await v.json()); if (c.ok) setCalls(await c.json());
  }
  useEffect(() => { void load(); const timer = window.setInterval(() => { void load(); }, 10000); return () => window.clearInterval(timer); }, [token]);
  useEffect(() => {
    if (!('speechSynthesis' in window) || !remindersEnabled) return;
    for (const item of reminders.filter(r => r.status === 'in_progress' && !spokenReminders.current.has(r.id))) {
      const deadline = deadlines.find(d => d.id === item.deadline_id);
      if (!deadline) continue;
      spokenReminders.current.add(item.id);
      const utterance = new SpeechSynthesisUtterance(`Reminder: ${deadline.title}. Would you like to open the bilingual voice assistant?`);
      utterance.lang = language === 'auto' ? 'te-IN' : language;
      window.speechSynthesis.speak(utterance);
    }
  }, [reminders, deadlines, language, remindersEnabled]);
  useEffect(() => { if (tab === 'preferences' && token) { void fetch(`${API}/preferences`, { headers: auth }).then(r => r.json()).then(p => { setLanguage(p.language); setConsent(p.consent); setRemindersEnabled(p.reminders_enabled); }); void fetch(`${API}/telephony/status`, { headers: auth }).then(r => r.json()).then(p => setCallStatus(p.blockers || [])); } }, [tab, token]);
  async function add(e: React.FormEvent) {
    e.preventDefault();
    const result = await fetch(`${API}/deadlines`, { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ title, kind, delivery_mode: deliveryMode, due_at: new Date(due).toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, reminder_minutes_before: reminderMinutes }) });
    setMessage(result.ok ? 'Deadline saved and reminder scheduled.' : await result.text()); if (result.ok) { setTitle(''); setDue(''); await load(); }
  }
  async function action(reminderId: string, action: string) {
    const until = new Date(Date.now() + 30 * 60_000).toISOString();
    await fetch(`${API}/reminders/${reminderId}/action`, { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ action, ...(action === 'snooze' ? { until } : {}) }) }); await load();
  }
  async function sayTurn(reminderId: string) {
    const response = await fetch(`${API}/reminders/${reminderId}/voice-turn`, { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ transcript }) });
    const result = await response.json(); setReply(result.reply || result.detail || '');
    if (result.reply && 'speechSynthesis' in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance(result.reply));
    await load();
  }
  async function editDeadline(item: Deadline) {
    const nextTitle = window.prompt('Deadline title', item.title); if (!nextTitle?.trim()) return;
    const nextDue = window.prompt('Due date and time (ISO format)', item.due_at); if (!nextDue) return;
    const result = await fetch(`${API}/deadlines/${item.id}`, { method: 'PATCH', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ title: nextTitle, kind: item.kind, delivery_mode: item.delivery_mode || 'browser', due_at: new Date(nextDue).toISOString(), timezone: item.timezone, reminder_minutes_before: item.reminder_minutes_before }) });
    setMessage(result.ok ? 'Deadline updated.' : `Update failed: ${await result.text()}`); await load();
  }
  async function deleteDeadline(item: Deadline) {
    if (!window.confirm(`Delete “${item.title}”?`)) return;
    const result = await fetch(`${API}/deadlines/${item.id}`, { method: 'DELETE', headers: auth });
    setMessage(result.ok ? 'Deadline cancelled.' : `Delete failed: ${await result.text()}`); await load();
  }
  function listen() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) { setReply('Speech recognition is not supported in this browser. Type your response instead.'); return; }
    const recognition = new SpeechRecognition(); recognition.lang = language === 'auto' ? 'te-IN' : language; recognition.onresult = (event: any) => setTranscript(event.results[0][0].transcript); recognition.start();
  }
  async function savePreferences() {
    await fetch(`${API}/preferences`, { method: 'PUT', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, language, reminders_enabled: remindersEnabled, voice_enabled: true, call_enabled: consent, consent }) });
    const status = await fetch(`${API}/telephony/status`, { headers: auth }).then(r => r.json()); setCallStatus(status.blockers || []); setMessage('Preferences saved. Phone calls remain disabled until all configuration checks pass.');
  }
  async function authenticate(e: React.FormEvent) {
    e.preventDefault(); setAuthError('');
    try {
      const response = await fetch(`${API}/auth/${authMode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: authEmail, password: authPassword }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Authentication failed');
      localStorage.setItem('accessToken', result.access_token); setToken(result.access_token); await load(result.access_token);
    } catch (error) { setAuthError(error instanceof Error ? error.message : 'Authentication failed'); }
  }
  function signOut() { localStorage.removeItem('accessToken'); setToken(''); setDeadlines([]); setReminders([]); }
  if (!token) return <main><aside><div className="brand">B<span>·</span></div><div className="nav">◫<br/>▦<br/>◷</div><small>LEARN</small></aside><section className="content"><header><div><span className="eyebrow">FEATURE 2 DEMO</span><h1>Deadline reminders</h1></div></header><div className="card auth-card"><span className="eyebrow">STUDENT ACCOUNT</span><h2>{authMode==='login'?'Welcome back':'Create demo account'}</h2><p>This isolated Feature 2 demo uses its own account store. It is not connected to production BHASHALEARN login.</p><form onSubmit={authenticate}><label>Email<input type="email" required autoComplete="email" value={authEmail} onChange={e=>setAuthEmail(e.target.value)}/></label><label>Password<input type="password" required minLength={authMode==='register'?12:1} autoComplete={authMode==='login'?'current-password':'new-password'} value={authPassword} onChange={e=>setAuthPassword(e.target.value)}/></label><button className="primary">{authMode==='login'?'Sign in':'Create account'}</button>{authError&&<small className="error">{authError}</small>}</form><button className="link" onClick={()=>setAuthMode(authMode==='login'?'register':'login')}>{authMode==='login'?'New here? Create a demo account':'Already registered? Sign in'}</button></div></section></main>;
  return <main><aside><div className="brand">B<span>·</span></div><div className="nav">◫<br/>▦<br/>◷</div><small>LEARN</small></aside><section className="content"><header><div><span className="eyebrow">YOUR STUDY SPACE</span><h1>Deadline reminders</h1></div><div className="profile">Student <button className="signout" onClick={signOut}>Sign out</button><span>●</span></div></header>
    <div className="tabs">{['upcoming','calendar','history','preferences'].map(x => <button className={tab===x?'selected':''} onClick={()=>setTab(x)} key={x}>{x[0].toUpperCase()+x.slice(1)}</button>)}</div>
    {tab==='upcoming' && <><div className="grid"><div><div className="sectiontitle"><div><span className="eyebrow">STAY ON TRACK</span><h2>Coming up</h2></div><span className="count">{deadlines.length} deadlines</span></div>{deadlines.map(d=><article key={d.id}><div className="icon">{d.kind==='exam'?'✦':'▤'}</div><div className="item"><b>{d.title}</b><small>{d.kind} · {new Date(d.due_at).toLocaleString()} · reminder {d.reminder_minutes_before}m before</small></div><span className={d.completed_at?'done':'status'}>{d.completed_at?'Completed':'Upcoming'}</span><button onClick={()=>editDeadline(d)}>Edit</button><button onClick={()=>deleteDeadline(d)}>Delete</button></article>)}{!deadlines.length&&<div className="empty">Your deadlines will appear here.</div>}{message&&<p role="status">{message}</p>}</div>
    <div className="card"><span className="eyebrow">ADD A REMINDER</span><h2>Keep it on your radar</h2><form onSubmit={add}><label>What’s due?<input required value={title} onChange={e=>setTitle(e.target.value)} placeholder="e.g. Algebra assignment"/></label><label>Type<select value={kind} onChange={e=>setKind(e.target.value)}><option value="assignment">Assignment</option><option value="exam">Exam</option></select></label><label>Delivery<select value={deliveryMode} onChange={e=>setDeliveryMode(e.target.value as 'browser'|'call')}><option value="browser">Browser voice reminder</option><option value="call">Phone call (requires consent and verified test number)</option></select></label><label>Due date and time<input required type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label><label>Remind me<select value={reminderMinutes} onChange={e=>setReminderMinutes(Number(e.target.value))}><option value={10}>10 minutes before</option><option value={30}>30 minutes before</option><option value={60}>1 hour before</option><option value={1440}>24 hours before</option></select></label><button className="primary">Add deadline <span>→</span></button>{message&&<small>{message}</small>}</form></div></div>
      {reminders.filter(r=>r.status==='in_progress').map(r=>{const deadline=deadlines.find(d=>d.id===r.deadline_id); return <div className="card voice" key={r.id}><span className="eyebrow">REMINDER DUE</span><h2>{deadline?.title || 'Your deadline'}</h2><p>Speak with the LiveKit voice agent, or use the browser speech fallback if LiveKit is not configured.</p><LiveKitReminder reminderId={r.id} language={language==='auto'?'mixed':language}/><div className="voicebox"><input value={transcript} onChange={e=>setTranscript(e.target.value)} placeholder="Remind me in 30 minutes…"/><button onClick={listen}>🎙 Speak</button><button className="primary" onClick={()=>sayTurn(r.id)}>Send response</button><button onClick={()=>action(r.id,'completed')}>Mark completed</button></div>{reply&&<blockquote>{reply}</blockquote>}</div>})}</>}
    {tab==='calendar'&&<div className="card"><h2>Reminder calendar</h2>{deadlines.map(d=><p key={d.id}>{new Date(d.due_at).toLocaleDateString()} · {d.title}</p>)}</div>}
    {tab==='history'&&<div className="card"><h2>Reminder history</h2>{reminders.map(r=><article key={r.id}><span>{new Date(r.scheduled_at).toLocaleString()}</span><span className="status">{r.status}</span><button onClick={()=>action(r.id,'acknowledge')}>Acknowledge</button><button onClick={()=>action(r.id,'snooze')}>Snooze 30m</button><button onClick={()=>action(r.id,'completed')}>Completed</button></article>)}<h3>Browser voice sessions</h3>{voiceSessions.map(s=><article key={s.id}><span>{new Date(s.created_at).toLocaleString()}</span><span className="status">{s.status} · {s.language}</span></article>)}<h3>Phone call history</h3>{calls.map(c=><article key={c.id}><span>{new Date(c.created_at).toLocaleString()}</span><span className="status">{c.status}</span>{c.failure&&<small>{c.failure}</small>}</article>)}</div>}
    {tab==='preferences'&&<div className="card"><h2>Language & call preferences</h2><p>Choose the language for reminder conversations. Phone calls stay disabled until consent, number verification, approved caller identity and SIP credentials are configured.</p><select aria-label="Language" value={language} onChange={e=>setLanguage(e.target.value)}><option value="te-IN">తెలుగు · Telugu</option><option value="en-IN">English</option><option value="auto">తెలుగు + English</option></select><label className="consent"><input type="checkbox" checked={remindersEnabled} onChange={e=>setRemindersEnabled(e.target.checked)}/> Enable browser deadline reminders</label><label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> I consent to deadline reminder calls when calling is configured. I can turn this off anytime.</label><button className="primary" onClick={savePreferences}>Save preferences</button>{callStatus.length>0&&<ul>{callStatus.map(item=><li key={item}>{item}</li>)}</ul>}{message&&<small>{message}</small>}</div>}
    <footer>Made for steady progress <span>✳</span></footer></section></main>
}
const root = document.getElementById('root');
if (root) createRoot(root).render(<App/>);
