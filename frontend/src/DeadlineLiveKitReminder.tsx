import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track, type RemoteTrack, type RemoteTrackPublication, type RemoteParticipant } from "livekit-client";
import { getToken, request } from "./auth";

type Deadline = { id: string; title: string; due_at: string; status: string };
type SessionPayload = { session_id: string; server_url: string; participant_token: string; provider_mode: string };
type SessionHistory = { id: string; deadline_id: string; status: string; language: string; created_at: string; ended_at: string | null };

export function DeadlineLiveKitReminder({ deadlines }: { deadlines: Deadline[] }) {
  const [language, setLanguage] = useState("mixed");
  const [activeDeadline, setActiveDeadline] = useState<Deadline | null>(null);
  const [busyId, setBusyId] = useState("");
  const [state, setState] = useState("Ready");
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [callResult, setCallResult] = useState("");
  const [history, setHistory] = useState<SessionHistory[]>([]);
  const roomRef = useRef<Room | null>(null);
  const sessionRef = useRef("");
  const token = getToken();

  useEffect(() => {
    if (token) void request<SessionHistory[]>("/assistant/livekit-sessions", { headers: { Authorization: `Bearer ${token}` } }).then(setHistory).catch(() => undefined);
    return () => {
      void roomRef.current?.disconnect();
      if (token && sessionRef.current) void request(`/assistant/livekit-sessions/${encodeURIComponent(sessionRef.current)}/close`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined);
    };
  }, [token]);

  async function start(deadline: Deadline) {
    if (!token || busyId) return;
    setBusyId(deadline.id); setError(""); setState("Creating secure voice room…");
    let created: SessionPayload | null = null;
    try {
      created = await request<SessionPayload>(`/assistant/deadlines/${encodeURIComponent(deadline.id)}/livekit-session`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ language }),
      });
      const room = new Room({ adaptiveStream: true, dynacast: true });
      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _publication: RemoteTrackPublication, _participant: RemoteParticipant) => {
        if (track.kind !== Track.Kind.Audio) return;
        const element = track.attach(); element.autoplay = true; element.setAttribute("aria-label", "AI reminder voice");
        document.body.appendChild(element);
      });
      room.on(RoomEvent.Disconnected, () => setState("Disconnected"));
      roomRef.current = room;
      await room.connect(created.server_url, created.participant_token);
      await room.localParticipant.setMicrophoneEnabled(true);
      sessionRef.current = created.session_id;
      setSessionId(created.session_id); setActiveDeadline(deadline); setState("Connected · speak naturally");
    } catch (cause) {
      await roomRef.current?.disconnect(); roomRef.current = null;
      if (created) await request(`/assistant/livekit-sessions/${encodeURIComponent(created.session_id)}/close`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      }).catch(() => undefined);
      setError(cause instanceof Error ? cause.message : "Could not start the LiveKit reminder."); setState("Not connected");
    } finally { setBusyId(""); }
  }

  async function stop() {
    if (!sessionId || !token) return;
    setBusyId("closing"); setError("");
    try {
      await roomRef.current?.localParticipant.setMicrophoneEnabled(false);
      await roomRef.current?.disconnect(); roomRef.current = null;
      await request(`/assistant/livekit-sessions/${encodeURIComponent(sessionId)}/close`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      });
      sessionRef.current = ""; setSessionId(""); setActiveDeadline(null); setState("Reminder conversation ended");
      const rows = await request<SessionHistory[]>("/assistant/livekit-sessions", { headers: { Authorization: `Bearer ${token}` } }); setHistory(rows);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not close the voice session."); }
    finally { setBusyId(""); }
  }

  async function placePhoneCall(deadline: Deadline) {
    if (!token || busyId) return;
    const accepted = window.confirm(`Place a reminder call to your verified number for “${deadline.title}”? This uses your saved call consent.`);
    if (!accepted) return;
    setBusyId(deadline.id); setCallResult(""); setError("");
    try {
      const result = await request<{ call_id: string; status: string; duplicate: boolean }>(
        `/assistant/deadlines/${encodeURIComponent(deadline.id)}/sip-call`, {
          method: "POST", headers: { Authorization: `Bearer ${token}` },
          body: JSON.stringify({ explicit_confirmation: true }),
        });
      setCallResult(`Phone call ${result.status}${result.duplicate ? " (existing attempt)" : ""}. Reference ${result.call_id}.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Phone call could not be started."); }
    finally { setBusyId(""); }
  }

  return <section className="as-card" aria-labelledby="livekit-reminders-title">
    <div className="as-heading"><span>LIVE BILINGUAL VOICE</span><h2 id="livekit-reminders-title">Deadline reminders</h2></div>
    <p className="as-muted">Join a private LiveKit room to speak with the reminder assistant. Your microphone starts only after you choose a deadline and join.</p>
    <label className="as-field">Conversation language<select value={language} onChange={event => setLanguage(event.target.value)} disabled={Boolean(sessionId)}>
      <option value="mixed">Telugu + English</option><option value="te">Telugu</option><option value="en">English</option>
    </select></label>
    <p role="status" aria-live="polite">Voice status: {state}{activeDeadline ? ` · ${activeDeadline.title}` : ""}</p>
    {error && <p className="as-error" role="alert">{error}</p>}
    {callResult && <p className="as-notice" role="status">{callResult}</p>}
    {history.length > 0 && <details><summary>Browser voice history ({history.length})</summary>{history.slice(0, 10).map(item => <p className="as-muted" key={item.id}>{new Date(item.created_at).toLocaleString()} · {item.language} · {item.status}</p>)}</details>}
    {sessionId ? <button className="as-primary" disabled={Boolean(busyId)} onClick={() => void stop()}>{busyId ? "Ending…" : "End voice reminder"}</button> : <ul className="as-list">
      {deadlines.filter(item => ["upcoming", "overdue"].includes(item.status)).map(item => <li key={item.id}>
        <div><strong>{item.title}</strong><small>{new Date(item.due_at).toLocaleString()}</small></div>
        <div className="as-actions"><button className="as-primary" disabled={Boolean(busyId)} onClick={() => void start(item)}>{busyId === item.id ? "Joining…" : "Start browser voice"}</button><button disabled={Boolean(busyId)} onClick={() => void placePhoneCall(item)}>Place consented phone call</button></div>
      </li>)}
      {!deadlines.some(item => ["upcoming", "overdue"].includes(item.status)) && <li><span>No active deadlines. Add one above to start a voice reminder.</span></li>}
    </ul>}
  </section>;
}
