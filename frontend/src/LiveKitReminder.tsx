import { useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001/api';

export function LiveKitReminder({ reminderId, language }: { reminderId: string; language: string }) {
  const [status, setStatus] = useState('idle'), [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const roomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLDivElement>(null);
  const token = () => localStorage.getItem('accessToken') || '';

  async function start() {
    setError(''); setStatus('connecting');
    try {
      const response = await fetch(`${API}/reminders/${reminderId}/voice-session`, {
        method: 'POST', headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ language }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.message || 'LiveKit is not configured.');
      const room = new Room({ adaptiveStream: true, dynacast: true });
      room.on(RoomEvent.TrackSubscribed, track => {
        if (track.kind === Track.Kind.Audio && audioRef.current) audioRef.current.appendChild(track.attach());
      });
      room.on(RoomEvent.Disconnected, () => setStatus('disconnected'));
      await room.connect(payload.server_url, payload.participant_token);
      await room.localParticipant.setMicrophoneEnabled(true);
      roomRef.current = room; setSessionId(payload.session_id); setStatus('connected');
    } catch (cause) {
      setStatus('idle'); setError(cause instanceof Error ? cause.message : 'Could not start the browser voice session.');
    }
  }

  async function stop() {
    const room = roomRef.current; roomRef.current = null;
    if (room) await room.disconnect();
    if (sessionId) await fetch(`${API}/voice/sessions/${sessionId}/close`, { method: 'POST', headers: { Authorization: `Bearer ${token()}` } }).catch(() => undefined);
    setStatus('ended');
  }

  useEffect(() => () => { if (roomRef.current) void roomRef.current.disconnect(); }, []);

  return <div className="livekit-control"><div ref={audioRef} className="remote-audio" />
    {status === 'connected' ? <><span className="live">● LiveKit connected · mic on</span><button onClick={stop}>End conversation</button></> : <button className="primary" disabled={status === 'connecting'} onClick={start}>{status === 'connecting' ? 'Connecting…' : status === 'ended' ? 'Start another voice reminder' : 'Start browser voice reminder'}</button>}
    {error && <small className="error" role="alert">{error}</small>}
  </div>;
}
