import { useState } from "react";
import { getToken, request } from "./auth";
import "./practice-assessment.css";

type Question = { attempt_id: string; topic: string; question_id: string; prompt: string; options: string[] };
type Result = { answer: string; is_correct: boolean | null; ambiguous: boolean; feedback: string; mastery_score: number | null; evidence_attempts: number; difficulty: string; strategy: string; recommendation: string; replayed: boolean };

export function PracticeAssessment({ sessionId }: { sessionId: string | null }) {
  const [question, setQuestion] = useState<Question | null>(null);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const headers = () => ({ Authorization: "Bearer " + getToken() });

  async function issue() {
    if (!sessionId || loading) return;
    setLoading(true); setError(""); setResult(null); setSelected("");
    try {
      const next = await request<Question>(`/assessments/sessions/${encodeURIComponent(sessionId)}/issue`, { method: "POST", headers: headers() });
      setQuestion(next);
    } catch (cause) {
      setQuestion(null);
      setError(cause instanceof Error ? cause.message : "Practice is not available for this topic yet.");
    } finally { setLoading(false); }
  }

  async function submit() {
    if (!question || !selected || loading) return;
    setLoading(true); setError("");
    try {
      const response = await request<Result>(`/assessments/${encodeURIComponent(question.attempt_id)}/answer`, {
        method: "POST", headers: headers(), body: JSON.stringify({ answer: selected }),
      });
      setResult(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit your answer.");
    } finally { setLoading(false); }
  }

  if (!sessionId) return null;
  return <section className="pa-card" aria-label="Objective practice assessment">
    <div className="pa-heading"><div><span>PERSONALIZED PRACTICE</span><h3>Check your understanding</h3><p>Only submitted objective answers update topic mastery.</p></div><button type="button" onClick={() => void issue()} disabled={loading}>{loading ? "Loading…" : question ? "New question ↗" : "Start practice ↗"}</button></div>
    {error && <p className="pa-error" role="alert">{error}</p>}
    {question && <div className="pa-question"><strong>{question.prompt}</strong><div className="pa-options">{question.options.map(option => <button type="button" key={option} className={selected === option ? "pa-option pa-selected" : "pa-option"} disabled={!!result || loading} onClick={() => setSelected(option)}>{option}</button>)}</div>{!result && <button type="button" className="pa-submit" disabled={!selected || loading} onClick={() => void submit()}>Submit answer</button>}</div>}
    {result && <div className="pa-result" role="status"><strong>{result.ambiguous ? "Let's clarify that answer" : result.is_correct ? "Correct! Well done." : "Good try — let's learn from it."}</strong><p>{result.feedback}</p><div className="pa-evidence">{result.mastery_score === null ? "Mastery not assessed yet" : `Topic mastery: ${result.mastery_score}%`} · {result.evidence_attempts} scored answers · {result.difficulty}</div><p className="pa-next">{result.recommendation}</p></div>}
  </section>;
}
