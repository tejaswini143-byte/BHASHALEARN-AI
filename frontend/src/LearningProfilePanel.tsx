import type { LearningPace, LearningPreferences, LearningProfile } from "./learningPreferences";

type Props = {
  preferences: LearningPreferences;
  profile: LearningProfile | null;
  loading: boolean;
  error: string;
  disabled: boolean;
  onPaceChange: (pace: LearningPace) => void;
};

export function LearningProfilePanel({ preferences, profile, loading, error, disabled, onPaceChange }: Props) {
  return <section className="cl-learning-profile" aria-label="Your learning profile">
    <div className="cl-profile-controls">
      <label htmlFor="cl-learning-pace">Learning pace</label>
      <select id="cl-learning-pace" value={preferences.learning_pace} disabled={disabled} onChange={event => onPaceChange(event.target.value as LearningPace)}>
        <option value="slow">Slow — one step at a time</option>
        <option value="steady">Steady — balanced examples</option>
        <option value="fast">Fast — brisk review</option>
      </select>
      {loading && <span role="status">Loading learning profile…</span>}
    </div>
    {error ? <p role="alert">{error}</p> : profile && <div className="cl-profile-summary" aria-live="polite">
      {profile.proficiencies.length ? profile.proficiencies.slice(0, 3).map(item => <article key={item.topic}>
        <strong>{item.topic}: {item.mastery_score}% mastery</strong>
        <span>{item.evidence_attempts} scored answers · {item.difficulty} practice</span>
        <p>{item.recommendation}</p>
      </article>) : <p>No scored progress yet. A short practice check will help build your learning profile.</p>}
      {profile.revision_topics.length > 0 && <p>Suggested review: {profile.revision_topics.join(", ")}</p>}
      {profile.recent_activity.length > 0 && <p>Recent activity: {profile.recent_activity.slice(0, 3).map(item => `${item.topic} — ${item.outcome}`).join(" · ")}</p>}
    </div>}
  </section>;
}
