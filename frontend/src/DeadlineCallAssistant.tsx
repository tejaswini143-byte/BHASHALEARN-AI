import { useCallback, useEffect, useRef, useState } from "react";
import { getToken, request } from "./auth";
import { wavFromFloatChunks } from "./voiceWav";
import "./deadline-call.css";

type Call = { id: string; deadline_id: string | null; title: string; status: string; language: string; max_duration_minutes: number; created_at: string; answered_at?: string | null; greeting?: string | null };
type Deadline = { id: string; title: string; due_at: string; timezone_name: string; status: string };
type Settings = { timezone: string; preferred_language: "en" | "te" | "mixed"; max_call_duration_minutes: 5 | 10 | 20 | 30 | 60; notifications: Record<string, boolean>; paused: boolean };
type Turn = { reply: string; language: string; proposed_reminder_at: string | null };
const headers = () => ({ Authorization: "Bearer " + getToken() });
const message = (error: unknown) => error instanceof Error ? error.message : "The deadline call failed.";

export function DeadlineCallAssistant() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [incoming, setIncoming] = useState<Call | null>(null);
  const [history, setHistory] = useState<Call[]>([]);
  const [reply, setReply] = useState("");
  const [draft, setDraft] = useState("");
  const [retryTurn, setRetryTurn] = useState<{ text: string; turnId: string } | null>(null);
  const [proposedAt, setProposedAt] = useState("");
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [companionStatus, setCompanionStatus] = useState("not connected");
  const [recording, setRecording] = useState(false);
  const chunks = useRef<Float32Array[]>([]);
  const capture = useRef<{ stream: MediaStream; context: AudioContext; source: MediaStreamAudioSourceNode; processor: ScriptProcessorNode; mute: GainNode } | null>(null);
  const microphoneAuthorization = useRef<string | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string | null>(null);

  const refreshPending = useCallback(async () => {
    try {
      const calls = await request<Call[]>("/assistant/local-calls/pending", { headers: headers() });
      setHistory(old => [...calls, ...old.filter(item => !calls.some(next => next.id === item.id) && item.status !== "ringing")].slice(0, 20));
      setIncoming(old => old?.status === "ringing" ? old : calls[0] || null);
    } catch (cause) { setError(message(cause)); }
  }, []);

  useEffect(() => {
    let live = true;
    void request<Settings>("/assistant/settings", { headers: headers() }).then(value => {
      if (!live) return;
      setSettings(value);
      if (value.notifications?.desktop_call && !value.paused) void refreshPending();
    }).catch(cause => { if (live) setError(message(cause)); });
    return () => { live = false; };
  }, [refreshPending]);

  useEffect(() => {
    if (!settings?.notifications?.desktop_call || settings.paused) return;
    const timer = window.setInterval(() => void refreshPending(), 5000);
    return () => window.clearInterval(timer);
  }, [settings?.notifications?.desktop_call, settings?.paused, refreshPending]);

  useEffect(() => {
    if (incoming?.status !== "answered" || !incoming.answered_at) return;
    const answeredAt = new Date(incoming.answered_at).getTime();
    const remaining = answeredAt + incoming.max_duration_minutes * 60_000 - Date.now();
    const timer = window.setTimeout(() => { void finish("end"); }, Math.max(0, remaining));
    return () => window.clearTimeout(timer);
  }, [incoming?.id, incoming?.status, incoming?.answered_at, incoming?.max_duration_minutes]);

  useEffect(() => () => {
    const active = capture.current;
    if (active) { active.processor.disconnect(); active.source.disconnect(); active.mute.disconnect(); active.stream.getTracks().forEach(track => track.stop()); void active.context.close(); }
    player.current?.pause();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
  }, []);

  async function saveDesktopCallSetting(enabled: boolean) {
    if (!settings || busy) return;
    setBusy(true); setError("");
    try {
      const next = await request<Settings>("/assistant/settings", { method: "PATCH", headers: headers(), body: JSON.stringify({
        notifications: { ...settings.notifications, desktop_call: enabled },
      }) });
      setSettings(next);
      if (enabled) await refreshPending();
      else if (companionStatus === "connected") await configureCompanion(false);
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }

  async function configureCompanion(enabled: boolean) {
    setError("");
    try {
      const base = import.meta.env.VITE_DESKTOP_COMPANION_BASE || "http://127.0.0.1:18767";
      const pairResponse = await fetch(base + "/pair", { mode: "cors", cache: "no-store" });
      const pair = await pairResponse.json() as { token?: string; error?: string };
      if (!pairResponse.ok || !pair.token) throw new Error(pair.error || "Start the local Windows companion first.");
      const response = await fetch(base + (enabled ? "/background/enable" : "/background/disable"), {
        method: "POST", mode: "cors", headers: { Authorization: "Bearer " + pair.token, "Content-Type": "application/json" },
        body: JSON.stringify(enabled ? { api_base: window.location.origin + "/api/v1", access_token: getToken() } : {}),
      });
      const result = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(result.error || "Windows companion could not be configured.");
      setCompanionStatus(enabled ? "connected" : "not connected");
      setNotice(enabled ? "Windows companion connected. It will poll this student session while the browser is closed." : "Windows background reminders disconnected.");
    } catch (cause) {
      setCompanionStatus("unavailable");
      setError(message(cause));
    }
  }

  async function saveTranscriptSetting(enabled: boolean) {
    if (!settings || busy) return;
    setBusy(true);
    try {
      const next = await request<Settings>("/assistant/settings", { method: "PATCH", headers: headers(), body: JSON.stringify({
        notifications: { ...settings.notifications, save_call_transcripts: enabled },
      }) });
      setSettings(next);
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }

  async function saveCallDuration(value: 5 | 10 | 20 | 30 | 60) {
    if (!settings || busy) return;
    setBusy(true); setError("");
    try {
      const next = await request<Settings>("/assistant/settings", { method: "PATCH", headers: headers(), body: JSON.stringify({ max_call_duration_minutes: value }) });
      setSettings(next); setNotice(`New calls may continue for up to ${value} minutes.`);
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }

  async function extendCall(additionalMinutes = 10) {
    if (!incoming || incoming.status !== "answered" || busy) return;
    setBusy(true); setError("");
    try {
      const next = await request<Call>("/assistant/local-calls/" + encodeURIComponent(incoming.id) + "/extend", {
        method: "POST", headers: headers(), body: JSON.stringify({ additional_minutes: additionalMinutes }),
      });
      setIncoming(next); setNotice(`Call extended. New limit: ${next.max_duration_minutes} minutes.`);
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }

  async function startTestCall() {
    if (busy) return;
    setBusy(true); setError(""); setReply(""); setProposedAt("");
    try {
      const deadline = await request<Deadline>("/assistant/deadlines", { method: "POST", headers: headers(),
        body: JSON.stringify({ title: "Disposable Feature 2 acceptance reminder", description: "Synthetic local Test Call only", due_at: new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(), timezone: settings?.timezone || "Asia/Kolkata", priority: "normal", category: "qa" }) });
      const call = await request<Call>("/assistant/local-calls/test", { method: "POST", headers: headers(),
        body: JSON.stringify({ language: settings?.preferred_language || "en", deadline_id: deadline.id }) });
      setIncoming(call); setState("ringing"); setHistory(old => [call, ...old.filter(item => item.id !== call.id)].slice(0, 20));
      try {
        const context = new AudioContext(); const oscillator = context.createOscillator(); const gain = context.createGain();
        oscillator.frequency.value = 880; gain.gain.value = 0.035; oscillator.connect(gain); gain.connect(context.destination);
        oscillator.start(); window.setTimeout(() => { oscillator.stop(); void context.close(); }, 350);
      } catch { /* Browser audio can be blocked until a user gesture. The visible call still rings. */ }
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }

  async function speak(text: string, language: string) {
    player.current?.pause();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    const response = await fetch("/api/v1/assistant/voice/speech", { method: "POST",
      headers: { ...headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }) });
    if (!response.ok) throw new Error("Gnani Timbre speech synthesis failed.");
    if (!response.headers.get("content-type")?.toLowerCase().startsWith("audio/wav")) throw new Error("Timbre returned an unsupported audio format.");
    const blob = await response.blob();
    if (!blob.size || !player.current) throw new Error("Timbre returned empty audio.");
    objectUrl.current = URL.createObjectURL(blob); player.current.src = objectUrl.current;
    await player.current.play(); setState("speaking");
  }

  async function answer() {
    if (!incoming || busy) return;
    setBusy(true); setError(""); setState("thinking");
    try {
      const call = await request<Call>("/assistant/local-calls/" + encodeURIComponent(incoming.id) + "/answer", {
        method: "POST", headers: { ...headers(), "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() },
        body: JSON.stringify({ explicit_user_action: true, initiating_component: "browser_answer_button" }),
      });
      setIncoming(call);
      if (!call.greeting) throw new Error("Gemini did not return an opening response.");
      setReply(call.greeting);
      try { await speak(call.greeting, call.language); setState("answered"); }
      catch (cause) { setError(message(cause)); setState("answered"); }
    } catch (cause) { setError(message(cause)); setState("failed"); } finally { setBusy(false); }
  }

  async function finish(action: "snooze" | "dismiss" | "end") {
    if (!incoming || busy) return;
    setBusy(true); setError(""); player.current?.pause();
    try {
      const body = action === "snooze" ? JSON.stringify({ minutes: 10 }) : undefined;
      const next = await request<Call>("/assistant/local-calls/" + encodeURIComponent(incoming.id) + "/" + action, {
        method: "POST", headers: { ...headers(), ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body } : {}),
      });
      setHistory(old => [next, ...old.filter(item => item.id !== next.id)].slice(0, 20));
      setIncoming(null); setState(next.status); setReply(""); setDraft(""); setProposedAt("");
      setRetryTurn(null);
      microphoneAuthorization.current = null;
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }

  async function startListening() {
    if (!incoming || incoming.status !== "answered" || busy || recording) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioContext === "undefined") { setError("Microphone recording is unavailable in this browser."); return; }
    try {
      player.current?.pause();
      const authorization = await request<{ authorization: string }>(
        "/assistant/local-calls/" + encodeURIComponent(incoming.id) + "/microphone", {
          method: "POST", headers: { ...headers(), "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() },
          body: JSON.stringify({ explicit_user_action: true, initiating_component: "browser_microphone_button" }),
        });
      microphoneAuthorization.current = authorization.authorization;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const context = new AudioContext(); await context.resume();
      const source = context.createMediaStreamSource(stream); const processor = context.createScriptProcessor(4096, 1, 1);
      const mute = context.createGain(); mute.gain.value = 0; chunks.current = [];
      processor.onaudioprocess = event => chunks.current.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      source.connect(processor); processor.connect(mute); mute.connect(context.destination);
      capture.current = { stream, context, source, processor, mute }; setRecording(true); setState("listening"); setError("");
    } catch (cause) { setError(cause instanceof DOMException && cause.name === "NotAllowedError"
      ? "Microphone permission was denied. Allow it in the browser to speak during the call." : message(cause)); }
  }

  async function stopListening() {
    const active = capture.current;
    if (!active || busy || !incoming) return;
    const callId = incoming.id;
    capture.current = null; setRecording(false); setBusy(true); setState("thinking");
    active.processor.onaudioprocess = null; active.processor.disconnect(); active.source.disconnect(); active.mute.disconnect();
    active.stream.getTracks().forEach(track => track.stop()); await active.context.close();
    try {
      const wav = wavFromFloatChunks(chunks.current, active.context.sampleRate);
      const form = new FormData(); form.append("audio", wav, "deadline-call.wav");
      const micToken = microphoneAuthorization.current; microphoneAuthorization.current = null;
      if (!micToken) throw new Error("Microphone authorization expired. Press Speak again.");
      form.append("microphone_authorization", micToken);
      const response = await fetch("/api/v1/assistant/local-calls/" + encodeURIComponent(callId) + "/transcribe", {
        method: "POST", headers: { ...headers(), "X-Request-ID": crypto.randomUUID() }, body: form,
      });
      if (!response.ok) throw new Error("Gnani Prisma transcription failed.");
      const result = await response.json() as { transcript?: string };
      if (!result.transcript?.trim()) throw new Error("Prisma returned an empty transcript.");
      setDraft(result.transcript); await sendTurn(result.transcript);
    } catch (cause) { setError(message(cause)); setState("answered"); } finally { setBusy(false); chunks.current = []; }
  }

  async function sendTurn(text: string, turnId: string = crypto.randomUUID()) {
    if (!incoming || !text.trim()) return;
    setBusy(true); setError(""); setRetryTurn(null); setState("thinking");
    try {
      const result = await request<Turn>("/assistant/local-calls/" + encodeURIComponent(incoming.id) + "/turn", {
        method: "POST", headers: headers(), body: JSON.stringify({ text: text.trim(), language: settings?.preferred_language || "mixed", turn_id: turnId }),
      });
      setReply(result.reply); setProposedAt(result.proposed_reminder_at || "");
      try { await speak(result.reply, settings?.preferred_language || "mixed"); setState("answered"); }
      catch (cause) { setError(message(cause)); setState("answered"); }
    } catch (cause) { setRetryTurn({ text: text.trim(), turnId }); setError(message(cause)); setState("answered"); } finally { setBusy(false); }
  }

  async function confirmReschedule() {
    if (!incoming || !proposedAt || busy) return;
    setBusy(true); setError("");
    try {
      const path = "/assistant/local-calls/" + encodeURIComponent(incoming.id) + "/reschedule";
      const reminder_at = new Date(proposedAt).toISOString();
      await request(path, { method: "POST", headers: headers(), body: JSON.stringify({ reminder_at, confirmed: false }) });
      await request(path, { method: "POST", headers: headers(), body: JSON.stringify({ reminder_at, confirmed: true }) });
      setNotice("Reminder saved. The local scheduler will ring at the confirmed time."); setProposedAt("");
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }

  const ringing = incoming?.status === "ringing";
  const answered = incoming?.status === "answered";
  return <section className="dc-card" aria-labelledby="dc-title">
    <div className="dc-heading"><span>WINDOWS REMINDER CALLS</span><h2 id="dc-title">Conversational deadline calls</h2></div>
    <p className="dc-copy">A BHASHALEARN application call on this device. This feature does not dial telephone numbers.</p>
    <label className="dc-optin"><input type="checkbox" checked={settings?.notifications?.desktop_call === true} disabled={!settings || busy} onChange={event => void saveDesktopCallSetting(event.target.checked)}/> Enable local Windows deadline calls</label>
    <label className="dc-optin"><input type="checkbox" checked={settings?.notifications?.save_call_transcripts === true} disabled={!settings || busy} onChange={event => void saveTranscriptSetting(event.target.checked)}/> Save call transcripts after calls (off by default)</label>
    <label className="dc-optin">Maximum conversation duration <select value={settings?.max_call_duration_minutes ?? 30} disabled={!settings || busy} onChange={event => void saveCallDuration(Number(event.target.value) as 5 | 10 | 20 | 30 | 60)}>{[5, 10, 20, 30, 60].map(minutes => <option key={minutes} value={minutes}>{minutes} minutes</option>)}</select></label>
    <p className="dc-privacy">Microphone audio is not saved. Conversation text is cleared when a call ends unless transcript saving is enabled.</p>
    <div className="dc-actions"><button type="button" onClick={() => void configureCompanion(true)} disabled={busy || !settings?.notifications?.desktop_call}>Connect Windows companion</button><button type="button" onClick={() => void configureCompanion(false)} disabled={busy || companionStatus !== "connected"}>Disconnect companion</button></div>
    <p className="dc-state">Windows companion: {companionStatus}. It must remain running for browser-closed ringing.</p>
    <button className="dc-primary" type="button" onClick={() => void startTestCall()} disabled={busy}>Start local Test Call</button>
    {settings?.paused && <p className="dc-state">Automation is paused; scheduled calls are disabled.</p>}
    {incoming && <div className={ringing ? "dc-call dc-ringing" : "dc-call"} role="region" aria-live="polite" aria-label="Deadline call">
      <p className="dc-state">{busy ? "THINKING" : state.toUpperCase()}</p><h3>BHASHALEARN AI — Deadline Call</h3><p>{incoming.title}</p>
      {ringing && <div className="dc-actions"><button onClick={event => { if (event.nativeEvent.isTrusted) void answer(); }} disabled={busy}>Answer</button><button onClick={() => void finish("snooze")} disabled={busy}>Snooze 10 min</button><button onClick={() => void finish("dismiss")} disabled={busy}>Dismiss</button></div>}
      {answered && <><blockquote>{reply}</blockquote>{draft && <p><strong>Prisma transcript:</strong> {draft}</p>}
        <p className="dc-state">Maximum call duration: {incoming.max_duration_minutes} minutes.</p>
        <div className="dc-actions"><button onClick={event => { if (event.nativeEvent.isTrusted) void (recording ? stopListening() : startListening()); }} disabled={busy}>{recording ? "Stop and send speech" : "Speak to BHASHALEARN"}</button><button onClick={() => void extendCall()} disabled={busy}>Extend +10 min</button><button onClick={() => void finish("end")} disabled={busy}>End Call</button></div>
        {retryTurn && <button type="button" onClick={() => void sendTurn(retryTurn.text, retryTurn.turnId)} disabled={busy}>Retry last turn</button>}
        <form className="dc-reply" onSubmit={event => { event.preventDefault(); void sendTurn(draft); }}><label>Text reply<input value={draft} onChange={event => setDraft(event.target.value)} maxLength={2000} placeholder="Type a response or speak"/></label><button type="submit" disabled={busy || !draft.trim()}>Send</button></form>
        {proposedAt && <div className="dc-confirm"><p>Proposed reminder time: {new Date(proposedAt).toLocaleString()}</p><button onClick={() => void confirmReschedule()} disabled={busy}>Confirm reminder</button><button onClick={() => setProposedAt("")}>Cancel</button></div>}
      </>}
    </div>}
    {error && <p className="dc-error" role="alert">{error}</p>}{notice && <p className="dc-notice" role="status">{notice}</p>}
    <audio ref={player} onEnded={() => { if (incoming?.status === "answered") setState("answered"); }} onError={() => { setError("Timbre audio could not be played."); setState("answered"); }}/>
    {history.length > 0 && <details className="dc-history"><summary>Recent local call history ({history.length})</summary>{history.map(call => <p key={call.id}>{new Date(call.created_at).toLocaleString()} · {call.title} · {call.status}</p>)}</details>}
  </section>;
}
