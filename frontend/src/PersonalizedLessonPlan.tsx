import { useCallback, useEffect, useState } from "react";
import { ApiError, getToken, request } from "./auth";
import { validatePersonalizedLesson, type PersonalizedLessonResponse } from "./personalizedTeaching";
import "./personalized-lesson.css";

type Props = { sessionId: string; language: string; onUnauthorized: () => void };
export function PersonalizedLessonPlan({ sessionId, language, onUnauthorized }: Props) {
  const [result, setResult] = useState<PersonalizedLessonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState("");
  const [notice, setNotice] = useState("");

  const loadPlan = useCallback(async (action?: "simpler" | "example" | "review", studentResponse?: string) => {
    setLoading(true); setError(""); setNotice("");
    try {
      const token = getToken();
      const response = await request<unknown>(`/tutor/sessions/${encodeURIComponent(sessionId)}/lesson-plan`, {
        method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: JSON.stringify({ ...(action ? { action } : {}), ...(studentResponse ? { student_response: studentResponse } : {}) }),
      });
      setResult(validatePersonalizedLesson(response));
      if (studentResponse) { setAnswer(""); setNotice("Thanks for trying the check. Your response does not change recorded mastery."); }
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) onUnauthorized();
      setError(cause instanceof Error ? cause.message : "Unable to prepare this lesson.");
    } finally { setLoading(false); }
  }, [sessionId, onUnauthorized]);

  useEffect(() => { void loadPlan(); }, [loadPlan, language]);
  const plan = result?.plan;
  return <section className="cl-personalized" aria-labelledby="cl-personalized-title">
    <div className="cl-personalized-head"><div><span className="cl-personalized-kicker">PERSONALIZED TEACHING</span><h2 id="cl-personalized-title">Your lesson plan</h2></div>
      {plan && <span className={`cl-difficulty cl-difficulty-${plan.difficulty}`} aria-label={`Difficulty: ${plan.difficulty}`}>{plan.difficulty}</span>}
    </div>
    {loading && <p className="cl-personalized-state" role="status">Preparing your personalized lesson…</p>}
    {error && <div className="cl-personalized-error" role="alert"><span>{error}</span><button onClick={() => void loadPlan()}>Retry</button></div>}
    {!loading && !error && plan && <>
      {plan.fallback && <p className="cl-plan-fallback" role="status">AI lesson service is unavailable. Showing a deterministic lesson plan.</p>}
      <article className="cl-plan-objective"><small>LEARNING OBJECTIVE</small><p>{plan.learning_objective}</p></article>
      <p className="cl-plan-evidence">{result?.learning_goal && <>Your saved goal: <strong>{result.learning_goal}</strong> · </>}{result?.evidence_attempts ? `Difficulty reflects ${result.evidence_attempts} scored practice answers.` : "Starting level: no scored practice history yet."}</p>
      <div className="cl-plan-grid">
        <article><h3>Start with</h3>{plan.prerequisite_concepts.length ? <ul>{plan.prerequisite_concepts.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p>No prerequisite is recorded.</p>}</article>
        <article><h3>How we’ll learn</h3><p>{plan.explanation_strategy}</p></article>
        <article><h3>Examples</h3><ul>{plan.examples.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></article>
        <article><h3>Understanding check</h3><ol>{plan.understanding_checks.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ol>
          <form onSubmit={event => { event.preventDefault(); if (answer.trim()) void loadPlan(undefined, answer.trim()); }}>
            <label htmlFor="cl-understanding-answer">Your response</label><textarea id="cl-understanding-answer" value={answer} maxLength={1000} onChange={event => setAnswer(event.target.value)} placeholder="Try an answer in your own words" />
            <button type="submit" disabled={!answer.trim() || loading}>Submit response</button>
          </form>
        </article>
      </div>
      <div className="cl-plan-next"><div><small>RECOMMENDED NEXT TOPIC</small><strong>{plan.recommended_topic || "Keep exploring"}</strong><p>{plan.recommendation_reason}</p></div><p>{plan.suggested_next_activity}</p></div>
      {result?.citations.length ? <p className="cl-plan-sources">Grounded in your authorized material: {result.citations.map(item => `${item.document_title}, p. ${item.page_number}`).join(" · ")}</p> : plan.grounded && <p className="cl-plan-sources">Grounded in course lesson material.</p>}
      {notice && <p className="cl-personalized-notice" role="status">{notice}</p>}
      <div className="cl-plan-actions" aria-label="Lesson adjustments"><span>Need a different approach?</span>
        <button disabled={loading} onClick={() => void loadPlan("simpler")}>Explain more simply</button>
        <button disabled={loading} onClick={() => void loadPlan("example")}>Give another example</button>
        <button disabled={loading} onClick={() => void loadPlan("review")}>Review prerequisites</button>
      </div>
    </>}
  </section>;
}
