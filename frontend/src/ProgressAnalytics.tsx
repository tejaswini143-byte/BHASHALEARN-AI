import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ApiError, clearToken, getToken, request } from "./auth";
import "./progress-analytics.css";

type TrendDay = { date: string; sessions: number; completed_assessments: number; mission_completions: number; activity_count: number };
type Analytics = {
  range_days: number; timezone: string;
  overview: { learning_sessions: number; completed_activities: number; completed_assessments: number; learning_time_minutes: number | null; learning_time_status: string };
  range_totals: { sessions: number; completed_assessments: number; mission_completions: number };
  trend: TrendDay[];
  topics: { topic: string; subject: string; mastery_score: number | null; scored_attempts: number; correct_attempts: number }[];
  subjects: { subject: string; mastery_score: number; scored_attempts: number }[];
  strengths: { topic: string; mastery_score: number; scored_attempts: number }[];
  improvement_areas: { topic: string; mastery_score: number; scored_attempts: number }[];
  mission: { xp: number; level: number; xp_into_level: number; xp_to_next_level: number; completed_missions: number; badges: string[] };
  streak: { days: number; as_of_utc_date: string; timezone: string; lower_bound: boolean };
  recent_activity: { kind: string; title: string; occurred_at: string; detail: string | null }[];
  recommendations: { topic: string | null; recommendation: string; reason: string }[];
  quiz_analytics: { available: boolean; integration: string };
};
const ranges = [7, 30, 90] as const;
type RangeDays = (typeof ranges)[number];
const dayLabel = (value: string) => new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(value + "T00:00:00Z"));

function ActivityChart({ trend }: { trend: TrendDay[] }) {
  const max = Math.max(1, ...trend.map(day => day.activity_count));
  const points = trend.map((day, index) => ({
    x: trend.length < 2 ? 50 : 10 + (index / (trend.length - 1)) * 80,
    y: 88 - (day.activity_count / max) * 66, day,
  }));
  const line = points.map(point => point.x + "," + point.y).join(" ");
  const area = points.length ? "10,90 " + line + " 90,90" : "";
  const middle = trend[Math.floor((trend.length - 1) / 2)];
  return <div className="pa-chart-wrap">
    <svg className="pa-chart" viewBox="0 0 100 100" role="img" aria-label={"Recorded learning activity across " + trend.length + " UTC calendar days"}>
      <title>Recorded learning activity by UTC day</title>
      {[22, 44, 66, 88].map(y => <line key={y} x1="10" x2="90" y1={y} y2={y} className="pa-gridline" />)}
      {area && <polygon points={area} className="pa-area" />}
      {points.length > 1 && <polyline points={line} className="pa-line" />}
      {points.map(point => <circle key={point.day.date} cx={point.x} cy={point.y} r="1.7" className="pa-point"><title>{dayLabel(point.day.date) + ": " + point.day.activity_count + " recorded activities"}</title></circle>)}
    </svg>
    <div className="pa-chart-labels" aria-hidden="true"><span>{trend[0] ? dayLabel(trend[0].date) : ""}</span><span>{middle ? dayLabel(middle.date) : ""}</span><span>{trend.length ? dayLabel(trend[trend.length - 1].date) : ""}</span></div>
    <div className="pa-legend"><span><i className="pa-legend-dot" /> Sessions, answered practice, and mission claims</span></div>
  </div>;
}

function MasteryBars({ items }: { items: Analytics["subjects"] }) {
  if (!items.length) return <p className="pa-muted">Subject mastery will appear after scored practice is recorded.</p>;
  return <div className="pa-mastery-bars">{items.map(item => <div key={item.subject} className="pa-mastery-row">
    <div className="pa-mastery-meta"><strong>{item.subject}</strong><span>{item.mastery_score}% · {item.scored_attempts} scored</span></div>
    <div className="pa-meter" role="progressbar" aria-label={item.subject + " mastery"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={item.mastery_score}><span style={{ width: item.mastery_score + "%" }} /></div>
  </div>)}</div>;
}

export function ProgressAnalyticsPage() {
  const [range, setRange] = useState<RangeDays>(7);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const token = getToken();

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true); setError(""); setOffline(false);
    request<Analytics>("/analytics?range_days=" + range, { headers: { Authorization: "Bearer " + token } })
      .then(result => { if (active) setData(result); })
      .catch(cause => {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) { clearToken(); return; }
        setError(cause instanceof Error ? cause.message : "Progress analytics could not be loaded.");
        setOffline(cause instanceof ApiError && cause.status === 0);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [range, retry, token]);

  const hasProgress = useMemo(() => Boolean(data && (data.overview.learning_sessions || data.overview.completed_activities || data.topics.length || data.mission.xp)), [data]);
  if (!token) return <Navigate to="/login" replace />;

  return <main className="pa-page">
    <header className="pa-header">
      <Link to="/dashboard" className="pa-brand"><span aria-hidden="true">✦</span> BHASHA<strong>LEARN</strong><small>AI</small></Link>
      <nav aria-label="Learning navigation"><Link to="/dashboard">Dashboard</Link><Link to="/memories">Memories</Link><Link to="/voice">Voice Tutor</Link><Link to="/immersive">Immersive Classroom</Link><Link to="/future-me">Future Me</Link><Link to="/missions">Mission Mode</Link></nav>
    </header>
    <section className="pa-hero">
      <div><span className="pa-eyebrow">LEARNING INTELLIGENCE</span><h1>Your progress, <span>in focus.</span></h1><p>Explore the learning activity and assessment evidence recorded in your account.</p></div>
      <div className="pa-streak"><span>UTC STREAK</span><strong>{loading ? "—" : data?.streak.days ?? 0}</strong><small>{data?.streak.lower_bound ? "At least " : "Consecutive days "}{data?.streak.as_of_utc_date ? "· as of " + data.streak.as_of_utc_date : ""}</small></div>
    </section>
    <div className="pa-controls"><div><span className="pa-eyebrow">ACTIVITY WINDOW</span><p>Calendar days in UTC, including today</p></div><div className="pa-range" role="group" aria-label="Activity date range">{ranges.map(days => <button key={days} type="button" aria-pressed={range === days} onClick={() => setRange(days)}>{days} days</button>)}</div></div>
    {loading && <div className="pa-state" role="status">Loading your recorded learning progress…</div>}
    {!loading && error && <div className="pa-state pa-error" role="alert"><h2>{offline ? "You’re offline" : "Progress could not load"}</h2><p>{offline ? "Live account analytics needs a connection. No sample student metrics are being shown." : error}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Try again</button></div>}
    {!loading && !error && data && <>
      <div className="pa-source-note"><span className="pa-live-dot" /> LIVE ACCOUNT DATA <span>Recorded learning events only</span></div>
      {!hasProgress && <section className="pa-empty" aria-labelledby="pa-empty-title"><span aria-hidden="true">✧</span><h2 id="pa-empty-title">Your learning story starts here</h2><p>Start a learning session or complete objective practice. Your dashboard will grow from events recorded in your account.</p><Link to="/classroom">Start learning <span aria-hidden="true">↗</span></Link></section>}
      <section className="pa-kpis" aria-label="Learning overview">
        <article><span>LEARNING SESSIONS</span><strong>{data.overview.learning_sessions}</strong><small>Recorded session starts</small></article>
        <article><span>COMPLETED ACTIVITIES</span><strong>{data.overview.completed_activities}</strong><small>Answered practice + unique mission claims</small></article>
        <article><span>STUDY TIME</span><strong>{data.overview.learning_time_minutes === null ? "Not recorded" : data.overview.learning_time_minutes + " min"}</strong><small>Session durations are not collected</small></article>
        <article><span>MISSION XP</span><strong>{data.mission.xp} <em>XP</em></strong><small>Level {data.mission.level} · {data.mission.completed_missions} missions claimed</small></article>
      </section>
      <div className="pa-grid">
        <section className="pa-card pa-activity"><div className="pa-card-head"><div><span className="pa-eyebrow">CONSISTENCY</span><h2>Activity trend</h2></div><span className="pa-chip">{range === 7 ? "WEEKLY" : range === 30 ? "MONTHLY" : "90 DAYS"}</span></div><ActivityChart trend={data.trend} /><p className="pa-chart-summary">{data.range_totals.sessions} sessions · {data.range_totals.completed_assessments} answered practice · {data.range_totals.mission_completions} mission claims in this window</p></section>
        <section className="pa-card"><div className="pa-card-head"><div><span className="pa-eyebrow">EVIDENCE BASED</span><h2>Subject mastery</h2></div><span className="pa-chip">SCORED PRACTICE</span></div><MasteryBars items={data.subjects} /></section>
        <section className="pa-card pa-mission-card"><div className="pa-card-head"><div><span className="pa-eyebrow">MISSION MODE</span><h2>XP &amp; level</h2></div><Link to="/missions">Open missions ↗</Link></div><div className="pa-level-row"><strong>Level {data.mission.level}</strong><span>{data.mission.xp_into_level}/100 XP to next level</span></div><div className="pa-meter pa-xp-meter" role="progressbar" aria-label="XP progress to next level" aria-valuemin={0} aria-valuemax={100} aria-valuenow={data.mission.xp_into_level}><span style={{ width: data.mission.xp_into_level + "%" }} /></div><p className="pa-muted">{data.mission.xp_to_next_level} XP to the next level · {data.mission.completed_missions} unique claims</p><div className="pa-badges" aria-label="Earned badges">{data.mission.badges.length ? data.mission.badges.map(badge => <span key={badge}>✦ {badge}</span>) : <span>No badges recorded yet</span>}</div></section>
        <section className="pa-card"><div className="pa-card-head"><div><span className="pa-eyebrow">PRACTICE SIGNALS</span><h2>Strengths</h2></div></div>{data.strengths.length ? <ul className="pa-topic-list">{data.strengths.map(item => <li key={item.topic}><span>{item.topic}<small>{item.scored_attempts} scored attempts</small></span><strong>{item.mastery_score}%</strong></li>)}</ul> : <p className="pa-muted">A strength appears after at least three scored answers on a topic.</p>}</section>
        <section className="pa-card"><div className="pa-card-head"><div><span className="pa-eyebrow">ROOM TO GROW</span><h2>Improvement areas</h2></div></div>{data.improvement_areas.length ? <ul className="pa-topic-list">{data.improvement_areas.map(item => <li key={item.topic}><span>{item.topic}<small>{item.scored_attempts} scored attempts</small></span><strong>{item.mastery_score}%</strong></li>)}</ul> : <p className="pa-muted">Scored topic evidence will show areas to revisit.</p>}</section>
        <section className="pa-card"><div className="pa-card-head"><div><span className="pa-eyebrow">ADAPTIVE NEXT STEPS</span><h2>Recommended for you</h2></div></div><ul className="pa-recommendations">{data.recommendations.map((item, index) => <li key={(item.topic || "start") + "-" + index}><span>{item.topic || "First learning baseline"}</span><p>{item.recommendation}</p><small>{item.reason}</small></li>)}</ul></section>
      </div>
      <section className="pa-card pa-timeline"><div className="pa-card-head"><div><span className="pa-eyebrow">RECENT EVENTS</span><h2>Learning timeline</h2></div><span className="pa-chip">UTC · up to 12 events</span></div>{data.recent_activity.length ? <ol>{data.recent_activity.map((event, index) => <li key={event.kind + "-" + event.occurred_at + "-" + index}><span className={"pa-event-dot pa-event-" + event.kind} aria-hidden="true" /><div><strong>{event.title}</strong>{event.detail && <small>{event.detail}</small>}</div><time dateTime={event.occurred_at}>{new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC", timeZoneName: "short" }).format(new Date(event.occurred_at))}</time></li>)}</ol> : <p className="pa-muted">Recorded session starts, answered practice, and mission claims will appear here.</p>}</section>
      {!data.quiz_analytics.available && <p className="pa-integration-note">Quiz result analytics can connect when the separate assessment integration is available. This dashboard currently uses recorded session, objective practice, and mission data.</p>}
    </>}
    <footer className="pa-footer"><Link to="/dashboard">← Back to dashboard</Link><span>Progress is calculated from your student-owned learning records.</span></footer>
  </main>;
}
