import { useState } from "react";
import { ApiError, getToken, request } from "./auth";
import type { LearningLanguage } from "./sessionContext";
import "./practice-assessment.css";

type Issued = { assessment_id: string; topic: string; question: string; choices: Record<string, string>; language: LearningLanguage };
type Result = {
  assessment_id: string; topic: string; question: string; submitted_answer: string;
  outcome: "correct" | "incorrect" | "ambiguous"; correct_answer: string; feedback: string;
  mastery_score: number | null; mastery_category: string; evidence_count: number;
  recommended_difficulty: string; teaching_strategy: string;
};

const authHeaders = () => ({ Authorization: "Bearer " + getToken() });

export function PracticeAssessment({ sessionId, language }: { sessionId: string; language: LearningLanguage }) {
  const [assessment, setAssessment] = useState<Issued | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isTelugu = language === "telugu";

  async function issue() {
    if (!sessionId || busy) return;
    setBusy(true); setError(""); setResult(null); setAnswer("");
    try {
      const next = await request<Issued>(`/tutor/sessions/${encodeURIComponent(sessionId)}/assessments`, { method: "POST", headers: authHeaders() });
      setAssessment(next);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 422 ? "Objective practice is not available for this topic yet." : cause instanceof Error ? cause.message : "Could not load a practice question.");
      setAssessment(null);
    } finally { setBusy(false); }
  }

  async function submit() {
    if (!assessment || !answer || busy) return;
    setBusy(true); setError("");
    try {
      const response = await request<Result>(`/tutor/sessions/${encodeURIComponent(sessionId)}/assessments/${encodeURIComponent(assessment.assessment_id)}/answer`, {
        method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json" }, body: JSON.stringify({ answer }),
      });
      setResult(response);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not record this answer. Retrying the same choice is safe."); }
    finally { setBusy(false); }
  }

  return <section className="practice-check" aria-label={isTelugu ? "అభ్యాస ప్రశ్న" : "Objective practice question"}>
    <div className="practice-check-heading"><div><span>{isTelugu ? "అభ్యాస ప్రశ్న" : "Practice check"}</span><small>{isTelugu ? "సమర్పించిన సమాధానం మాత్రమే అభ్యాస ఆధారంగా నమోదు అవుతుంది." : "Only a submitted answer updates learning evidence."}</small></div>
      {!assessment && <button type="button" disabled={busy} onClick={() => void issue()}>{busy ? "Loading..." : isTelugu ? "అభ్యాసం ప్రారంభించండి" : "Practice this topic"}</button>}
    </div>
    {error && <p className="practice-error" role="alert">{error}</p>}
    {assessment && <div className="practice-question">
      <p>{assessment.question}</p>
      <fieldset disabled={busy || Boolean(result)}><legend>{isTelugu ? "ఒక సమాధానాన్ని ఎంచుకోండి" : "Choose one answer"}</legend>
        {Object.entries(assessment.choices).map(([key, text]) => <label key={key}><input type="radio" name={`answer-${assessment.assessment_id}`} value={key} checked={answer === key} onChange={() => setAnswer(key)}/><span><b>{key}.</b> {text}</span></label>)}
        <label><input type="radio" name={`answer-${assessment.assessment_id}`} value="unsure" checked={answer === "unsure"} onChange={() => setAnswer("unsure")}/><span>{isTelugu ? "నాకు తెలియదు" : "I'm not sure"}</span></label>
      </fieldset>
      {!result && <button type="button" disabled={!answer || busy} onClick={() => void submit()}>{busy ? "Saving..." : isTelugu ? "సమాధానం సమర్పించండి" : "Submit answer"}</button>}
      {result && <div className={`practice-result practice-${result.outcome}`} role="status">
        <strong>{result.feedback}</strong>
        {result.outcome !== "ambiguous" && <p>{isTelugu ? "సరైన ఎంపిక" : "Correct option"}: {result.correct_answer}</p>}
        <p>{result.mastery_category === "not_assessed" ? (isTelugu ? "ఇంకా అంచనా వేయలేదు" : "Not assessed") : `${result.mastery_score?.toFixed(0)}% · ${result.evidence_count} ${isTelugu ? "స్కోర్ చేసిన ప్రశ్నలు" : "scored checks"}`} · {isTelugu ? "తదుపరి" : "Next"}: {result.teaching_strategy.replaceAll("_", " ")} ({result.recommended_difficulty})</p>
        <button type="button" disabled={busy} onClick={() => { setAssessment(null); setResult(null); setAnswer(""); }}>{isTelugu ? "మరొక ప్రశ్న" : "Another question"}</button>
      </div>}
    </div>}
  </section>;
}
