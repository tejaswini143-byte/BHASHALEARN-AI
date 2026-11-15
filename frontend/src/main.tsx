import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001/api';
const token = localStorage.getItem('accessToken') || '';
type Deadline = { id: string; title: string; kind: string; due_at: string; timezone: string; completed_at?: string | null };
type Reminder = { id: string; deadline_id: string; scheduled_at: string; status: string };

function App() {
  const [deadlines, setDeadlines] = useState<Deadline[]>([]), [reminders, setReminders] = useState<Reminder[]>([]);
  const [title, setTitle] = useState(''), [kind, setKind] = useState('assignment'), [due, setDue] = useState('');
  const [message, setMessage] = useState(''); const [tab, setTab] = useState('upcoming');
  const [transcript, setTranscript] = useState(''), [reply, setReply] = useState('');
  const [language, setLanguage] = useState('te-IN'), [consent, setConsent] = useState(false), [callStatus, setCallStatus] = useState<string[]>([]);
  const auth = { Authorization: `Bearer ${token}` };
  async function load() {
    if (!token) return;
    const headers = auth;
    const [d, r] = await Promise.all([fetch(`${API}/deadlines`, { headers }), fetch(`${API}/reminders`, { headers })]);
    if (d.ok) setDeadlines(await d.json()); if (r.ok) setReminders(await r.json());
  }
  useEffect(() => { void load(); const timer = window.setInterval(() => { void load(); }, 10000); return () => window.clearInterval(timer); }, []);
  useEffect(() => { if (tab === 'preferences' && token) { void fetch(`${API}/preferences`, { headers: auth }).then(r => r.json()).then(p => { setLanguage(p.language); setConsent(p.consent); }); void fetch(`${API}/telephony/status`, { headers: auth }).then(r => r.json()).then(p => setCallStatus(p.blockers || [])); } }, [tab]);
  async function add(e: React.FormEvent) {
    e.preventDefault();
    const result = await fetch(`${API}/deadlines`, { method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ title, kind, due_at: new Date(due).toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }) });
    setMessage(result.ok ? 'Deadline saved and reminder scheduled.' : 'Save failed. Sign in and confirm the API is available.'); setTitle(''); await load();
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
  function listen() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) { setReply('Speech recognition is not supported in this browser. Type your response instead.'); return; }
    const recognition = new SpeechRecognition(); recognition.lang = language === 'auto' ? 'te-IN' : language; recognition.onresult = (event: any) => setTranscript(event.results[0][0].transcript); recognition.start();
  }
  async function savePreferences() {
    await fetch(`${API}/preferences`, { method: 'PUT', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, language, voice_enabled: true, call_enabled: consent, consent }) });
    const status = await fetch(`${API}/telephony/status`, { headers: auth }).then(r => r.json()); setCallStatus(status.blockers || []); setMessage('Preferences saved. Phone calls remain disabled until all configuration checks pass.');
  }
  return <main><aside><div className="brand">B<span>·</span></div><div className="nav">◫<br/>▦<br/>◷</div><small>LEARN</small></aside><section className="content"><header><div><span className="eyebrow">YOUR STUDY SPACE</span><h1>Deadline reminders</h1></div><div className="profile">{token ? 'Student' : 'Sign in required'} <span>●</span></div></header>
    {!token && <div className="notice">Sign in through BHASHALEARN to use reminders. This isolated feature workspace expects the app access token in localStorage as <code>accessToken</code>.</div>}
    <div className="tabs">{['upcoming','calendar','history','preferences'].map(x => <button className={tab===x?'selected':''} onClick={()=>setTab(x)} key={x}>{x[0].toUpperCase()+x.slice(1)}</button>)}</div>
    {tab==='upcoming' && <div className="grid"><div><div className="sectiontitle"><div><span className="eyebrow">STAY ON TRACK</span><h2>Coming up</h2></div><span className="count">{deadlines.length} deadlines</span></div>{deadlines.map(d=><article key={d.id}><div className="icon">{d.kind==='exam'?'✦':'▤'}</div><div className="item"><b>{d.title}</b><small>{d.kind} · {new Date(d.due_at).toLocaleString()}</small></div><span className={d.completed_at?'done':'status'}>{d.completed_at?'Completed':'Upcoming'}</span></article>)}{!deadlines.length&&<div className="empty">Your deadlines will appear here.</div>}</div>
    <div className="card"><span className="eyebrow">ADD A REMINDER</span><h2>Keep it on your radar</h2><form onSubmit={add}><label>What’s due?<input required value={title} onChange={e=>setTitle(e.target.value)} placeholder="e.g. Algebra assignment"/></label><label>Type<select value={kind} onChange={e=>setKind(e.target.value)}><option value="assignment">Assignment</option><option value="exam">Exam</option></select></label><label>Due date and time<input required type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label><button className="primary">Add deadline <span>→</span></button>{message&&<small>{message}</small>}</form></div></div>}
    {tab==='calendar'&&<div className="card"><h2>Reminder calendar</h2>{deadlines.map(d=><p key={d.id}>{new Date(d.due_at).toLocaleDateString()} · {d.title}</p>)}</div>}
    {tab==='history'&&<div className="card"><h2>Reminder history</h2>{reminders.map(r=><article key={r.id}><span>{new Date(r.scheduled_at).toLocaleString()}</span><span className="status">{r.status}</span><button onClick={()=>action(r.id,'acknowledge')}>Acknowledge</button><button onClick={()=>action(r.id,'snooze')}>Snooze 30m</button></article>)}</div>}
    {tab==='history'&&reminders.some(r=>r.status==='in_progress')&&<div className="card voice"><span className="eyebrow">BROWSER VOICE REMINDER</span><h2>Talk through your next step</h2><p>Speak in Telugu or English, or type a response. Speech recognition uses your browser; replies are spoken aloud.</p><div className="voicebox"><input value={transcript} onChange={e=>setTranscript(e.target.value)} placeholder="Okay, I will submit it…"/><button onClick={listen}>🎙 Speak</button><button className="primary" onClick={()=>sayTurn(reminders.find(r=>r.status==='in_progress')!.id)}>Send</button></div>{reply&&<blockquote>{reply}</blockquote>}</div>}
    {tab==='preferences'&&<div className="card"><h2>Language & call preferences</h2><p>Choose the language for reminder conversations. Phone calls stay disabled until consent, number verification, approved caller identity and SIP credentials are configured.</p><select aria-label="Language" value={language} onChange={e=>setLanguage(e.target.value)}><option value="te-IN">తెలుగు · Telugu</option><option value="en-IN">English</option><option value="auto">తెలుగు + English</option></select><label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> I consent to deadline reminder calls when calling is configured. I can turn this off anytime.</label><button className="primary" onClick={savePreferences}>Save preferences</button>{callStatus.length>0&&<ul>{callStatus.map(item=><li key={item}>{item}</li>)}</ul>}{message&&<small>{message}</small>}</div>}
    <footer>Made for steady progress <span>✳</span></footer></section></main>
}
createRoot(document.getElementById('root')!).render(<App/>);
