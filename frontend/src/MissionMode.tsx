import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request } from "./auth";
import type { MissionOverview } from "./missionModel";
import { MissionCard } from "./MissionCard";
import "./mission-mode.css";

type ClaimResult = { xp_awarded: number; total_xp: number; level: number; replayed: boolean; feedback: string };

export function MissionMode() {
  const [token] = useState(getToken);
  const [ready, setReady] = useState(false);
  const [overview, setOverview] = useState<MissionOverview | null>(null);
  const [studentName, setStudentName] = useState("");
  const [loading, setLoading] = useState(true);
  const [claiming, setClaiming] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadMissions = useCallback(async (authToken: string) => {
    setError("");
    try {
      const data = await request<MissionOverview>("/missions", { headers: { Authorization: `Bearer ${authToken}` } });
      setOverview(data);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearToken(); setReady(false); }
      else setError(cause instanceof Error ? cause.message : "Couldn't load missions.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (!token) { setReady(true); setLoading(false); return; }
    let active = true;
    getCurrentStudent(token).then(student => {
      if (!active) return;
      setStudentName(student.display_name);
      setReady(true);
      void loadMissions(token);
    }).catch(() => {
      if (!active) return;
      clearToken();
      setReady(true);
    });
    return () => { active = false; };
  }, [token, loadMissions]);

  async function claim(missionId: string) {
    if (!token || claiming) return;
    setClaiming(missionId);
    setNotice("");
    setError("");
    try {
      const result = await request<ClaimResult>(`/missions/${encodeURIComponent(missionId)}/claim`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, body: "{}",
      });
      setNotice(result.feedback);
      await loadMissions(token);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn't claim this reward.");
      await loadMissions(token);
    } finally { setClaiming(""); }
  }

  if (ready && !token) return <Navigate to="/login" replace />;
  if (ready && !getToken()) return <Navigate to="/login" replace />;

  return <main className="mission-page">
    <header className="mission-header"><Link to="/dashboard" className="mission-brand"><span>✦</span> BHASHA<span>LEARN</span> AI</Link><nav aria-label="Mission navigation"><Link to="/dashboard">Dashboard</Link><Link to="/classroom">AI Classroom</Link></nav></header>
    <section className="mission-hero">
      <div><span className="mission-kicker">YOUR LEARNING QUESTS</span><h1>Mission <em>Mode</em></h1>
        <p>{studentName ? `Welcome back, ${studentName}. ` : ""}Turn each objective quiz into progress, XP, and new achievements.</p>
        <p className="mission-hint">Complete the matching objective quiz in AI Classroom, then refresh here to claim its reward.</p>
      </div>
      <div className="mission-level"><span>YOUR LEVEL</span><strong>{overview?.level ?? "—"}</strong><small>✦ {overview?.xp ?? 0} total XP</small>
        <div className="mission-level-track" role="progressbar" aria-label="Progress to next level" aria-valuemin={0} aria-valuemax={100} aria-valuenow={overview?.xp_into_level ?? 0}><div style={{ width: `${overview?.xp_into_level ?? 0}%` }} /></div>
        <small>{overview?.xp_to_next_level ?? 100} XP to next level</small></div>
    </section>
    {notice && <p className="mission-feedback" role="status">{notice}</p>}
    {error && <p className="mission-error" role="alert">{error} <button onClick={() => token && void loadMissions(token)}>Retry</button></p>}
    <section className="mission-badges" aria-label="Achievement badges"><div><span className="mission-kicker">ACHIEVEMENTS</span><h2>Badges earned</h2></div>
      {overview?.badges.length ? <div className="mission-badge-list">{overview.badges.map(badge => <span className="mission-badge" key={badge}>✦ {badge}</span>)}</div> : <p>Complete a mission to earn your first badge.</p>}</section>
    <section className="mission-list" aria-label="Available missions"><div className="mission-list-heading"><div><span className="mission-kicker">PICK YOUR NEXT CHALLENGE</span><h2>Active missions</h2></div><button type="button" onClick={() => token && void loadMissions(token)} disabled={loading}>{loading ? "Refreshing…" : "Refresh progress"}</button></div>
      {loading ? <p className="mission-loading" role="status">Loading your missions…</p> : overview?.missions.length ? <div className="mission-grid">{overview.missions.map(mission => <MissionCard key={mission.id} mission={mission} claiming={claiming === mission.id} onClaim={claim} />)}</div> : !error && <p className="mission-loading">No missions are available right now.</p>}
    </section>
    <footer className="mission-footer"><Link to="/dashboard">← Back to your learning dashboard</Link><span>Mission progress is saved to your student account.</span></footer>
  </main>;
}
