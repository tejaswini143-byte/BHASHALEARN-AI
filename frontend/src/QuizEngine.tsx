import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, getToken, request } from "./auth";
import { answeredCount, progressPercent, resultFeedback, type Quiz, type QuizQuestion, type QuizResults, type QuizSummary } from "./quizModel";
import "./quiz-engine.css";

type CatalogItem = { subject: string; topic: string; question_count: number; difficulties: string[] };
type CreatedQuiz = Quiz & { questions: QuizQuestion[] };

const headers = () => ({ Authorization: "Bearer " + (getToken() || "") });
const copy = {
  english: { subtitle: "A short check-in shaped around what you know.", label: "Quiz language", start: "Start assessment", submit: "Submit assessment", score: "Your result", strong: "Strong work. Keep stretching your skills.", building: "You are building a good foundation.", review: "Let’s revisit a few ideas together.", history: "Your recent attempts", retry: "Try another quiz", confirm: "Submit your answers now? You can’t change them afterward.", reviewArea: "Topics to review", strength: "What went well", empty: "Your completed quizzes will appear here.", offline: "Quiz service is offline. Your learning data is safe; try again when the service is available." },
  telugu: { subtitle: "మీకు తెలిసిన విషయాల ఆధారంగా చిన్న పరీక్ష.", label: "పరీక్ష భాష", start: "పరీక్ష ప్రారంభించండి", submit: "పరీక్ష సమర్పించండి", score: "మీ ఫలితం", strong: "చక్కగా చేశారు. మరింత ముందుకు సాగండి.", building: "మీ పునాది బలపడుతోంది.", review: "కొన్ని అంశాలను కలిసి మళ్లీ చూద్దాం.", history: "మీ ఇటీవలి ప్రయత్నాలు", retry: "మరొక పరీక్ష ప్రయత్నించండి", confirm: "ఇప్పుడు సమాధానాలు సమర్పించాలా? ఆ తర్వాత మార్చలేరు.", reviewArea: "మళ్లీ చూడాల్సిన అంశాలు", strength: "బాగా చేసినది", empty: "పూర్తి చేసిన పరీక్షలు ఇక్కడ కనిపిస్తాయి.", offline: "పరీక్ష సేవ ప్రస్తుతం అందుబాటులో లేదు. మీ అభ్యాస డేటా సురక్షితంగా ఉంది; తర్వాత మళ్లీ ప్రయత్నించండి." },
  mixed: { subtitle: "A short check-in shaped around what you know. / మీకు తెలిసిన విషయాల ఆధారంగా చిన్న పరీక్ష.", label: "Quiz language / పరీక్ష భాష", start: "Start assessment / పరీక్ష ప్రారంభించండి", submit: "Submit assessment / పరీక్ష సమర్పించండి", score: "Your result / మీ ఫలితం", strong: "Strong work. Keep stretching your skills. / చక్కగా చేశారు. మరింత ముందుకు సాగండి.", building: "You are building a good foundation. / మీ పునాది బలపడుతోంది.", review: "Let’s revisit a few ideas together. / కొన్ని అంశాలను కలిసి మళ్లీ చూద్దాం.", history: "Your recent attempts / మీ ఇటీవలి ప్రయత్నాలు", retry: "Try another quiz / మరొక పరీక్ష ప్రయత్నించండి", confirm: "Submit your answers now? / ఇప్పుడు సమాధానాలు సమర్పించాలా?", reviewArea: "Topics to review / మళ్లీ చూడాల్సిన అంశాలు", strength: "What went well / బాగా చేసినది", empty: "Your completed quizzes will appear here. / పూర్తి చేసిన పరీక్షలు ఇక్కడ కనిపిస్తాయి.", offline: "Quiz service is offline. / పరీక్ష సేవ ప్రస్తుతం అందుబాటులో లేదు." },
};

function QuestionInput({ question, value, disabled, onChange }: { question: QuizQuestion; value: string; disabled: boolean; onChange: (value: string) => void }) {
  if (question.options.length) return <fieldset className="qe-choices" disabled={disabled}><legend className="sr-only">Answer choices</legend>{question.options.map(option => <label className={value === option ? "qe-choice selected" : "qe-choice"} key={option}><input type="radio" name={question.attempt_id} value={option} checked={value === option} onChange={() => onChange(option)}/><span>{option}</span></label>)}</fieldset>;
  return <label className="qe-text-answer">{question.type === "fill_blank" ? "Fill in your answer" : "Your short answer"}<input value={value} onChange={event => onChange(event.target.value)} maxLength={500} disabled={disabled} autoComplete="off"/></label>;
}

export function QuizEngine() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [history, setHistory] = useState<QuizSummary[]>([]);
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("adaptive");
  const [language, setLanguage] = useState("mixed");
  const [questionCount, setQuestionCount] = useState(2);
  const [quiz, setQuiz] = useState<CreatedQuiz | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [active, setActive] = useState(0);
  const [results, setResults] = useState<QuizResults | null>(null);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const labels = copy[language as keyof typeof copy];
  const activeQuestion = quiz?.questions[active];
  const completedAnswers = useMemo(() => quiz ? answeredCount(quiz.questions, answers) : 0, [quiz, answers]);

  useEffect(() => {
    if (!getToken()) { navigate("/login", { replace: true }); return; }
    let current = true;
    Promise.all([
      request<CatalogItem[]>("/quizzes/catalog", { headers: headers() }),
      request<QuizSummary[]>("/quizzes/history", { headers: headers() }),
    ]).then(([items, attempts]) => {
      if (!current) return;
      setCatalog(items); setHistory(attempts);
      setTopic(items[0]?.topic || "");
    }).catch(cause => {
      if (!current) return;
      setError(cause instanceof ApiError && cause.status === 0 ? labels.offline : cause instanceof Error ? cause.message : labels.offline);
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [navigate]);

  async function startQuiz() {
    if (!topic || busy) return;
    setBusy(true); setError(""); setResults(null); setConfirmSubmit(false);
    try {
      const next = await request<CreatedQuiz>("/quizzes", { method: "POST", headers: headers(), body: JSON.stringify({ topic, difficulty, language, question_count: questionCount }) });
      setQuiz(next); setAnswers({}); setActive(0);
    } catch (cause) { setError(cause instanceof ApiError && cause.status === 0 ? labels.offline : cause instanceof Error ? cause.message : "Could not start the quiz."); }
    finally { setBusy(false); }
  }

  async function submitQuiz() {
    if (!quiz || busy || completedAnswers !== quiz.questions.length) return;
    setBusy(true); setError("");
    try {
      const result = await request<QuizResults>(`/quizzes/${encodeURIComponent(quiz.quiz_id)}/submit`, {
        method: "POST", headers: headers(), body: JSON.stringify({ answers: quiz.questions.map(question => ({ attempt_id: question.attempt_id, answer: answers[question.attempt_id].trim() })) }),
      });
      setResults(result); setConfirmSubmit(false);
      setHistory(current => [result, ...current.filter(item => item.quiz_id !== result.quiz_id)]);
    } catch (cause) { setError(cause instanceof ApiError && cause.status === 0 ? labels.offline : cause instanceof Error ? cause.message : "Could not submit your answers."); }
    finally { setBusy(false); }
  }

  async function openHistory(item: QuizSummary) {
    if (!item.completed || busy) return;
    setBusy(true); setError("");
    try { setResults(await request<QuizResults>(`/quizzes/${encodeURIComponent(item.quiz_id)}/results`, { headers: headers() })); setQuiz(null); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not open this result."); }
    finally { setBusy(false); }
  }

  const currentResultFeedback = results ? resultFeedback(results) : null;
  const incorrect = results?.questions.filter(question => !question.is_correct) || [];
  return <main className="qe-page">
    <header className="qe-header"><Link to="/dashboard" className="qe-brand"><span>✦</span> BHASHA<span>LEARN</span> AI</Link><Link to="/dashboard" className="qe-back">← Dashboard</Link></header>
    <div className="qe-shell">
      <section className="qe-intro"><span className="qe-eyebrow">✦ ADAPTIVE ASSESSMENT</span><h1>Quiz <span>your way.</span></h1><p>{labels.subtitle}</p></section>
      {error && <p className="qe-error" role="alert">{error}</p>}
      {loading ? <p className="qe-loading" role="status">Preparing your quiz space…</p> : <>
        {!quiz && !results && <section className="qe-panel qe-setup" aria-labelledby="qe-setup-title"><div className="qe-panel-head"><div><span className="qe-eyebrow">MAKE IT YOURS</span><h2 id="qe-setup-title">Choose a learning goal</h2></div><span className="qe-chip">ADAPTIVE</span></div>
          <div className="qe-form-grid">
            <label>Subject and topic<input list="qe-topic-options" value={topic} onChange={event => setTopic(event.target.value)} placeholder="e.g. equivalent fractions or photosynthesis"/><datalist id="qe-topic-options">{catalog.map(item => <option key={item.topic} value={item.topic}>{item.subject}</option>)}</datalist></label>
            <label>Difficulty<select value={difficulty} onChange={event => setDifficulty(event.target.value)}><option value="adaptive">Adaptive recommendation</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select><small>Based on your scored practice history when adaptive is selected.</small></label>
            <label>{labels.label}<select value={language} onChange={event => setLanguage(event.target.value)}><option value="mixed">తెలుగు + English</option><option value="telugu">తెలుగు</option><option value="english">English</option></select></label>
            <label>Question count<select value={questionCount} onChange={event => setQuestionCount(Number(event.target.value))}><option value={1}>1 question</option><option value={2}>2 questions</option></select></label>
          </div>
          <div className="qe-start-row"><p>Questions use Gemini when available. Curated questions are clearly labeled as a fallback. Explanations appear after submission.</p><button className="qe-primary" type="button" onClick={() => void startQuiz()} disabled={!topic.trim() || busy}>{busy ? "Preparing…" : labels.start} <span>↗</span></button></div>
        </section>}

        {quiz && !results && activeQuestion && <section className="qe-panel qe-quiz" aria-label="Quiz questions"><div className="qe-panel-head"><div><span className="qe-eyebrow">{quiz.subject.toUpperCase()} · {quiz.difficulty.toUpperCase()}</span><h2>{quiz.topic}</h2></div><button className="qe-link-button" type="button" onClick={() => { setQuiz(null); setAnswers({}); setError(""); }}>Exit quiz</button></div>
          <p role="note" style={{ fontSize: 11, color: "#91a4c7", margin: "0 0 12px" }}>{quiz.source === "gemini_live" ? "Generated by the live Gemini provider" : quiz.source === "curated" ? "Curated curriculum questions" : quiz.source === "deterministic_fallback" ? "Deterministic fallback questions" : "Curated and deterministic fallback questions"}</p>
          <div className="qe-progress-head"><span>Question {active + 1} of {quiz.questions.length}</span><span>{completedAnswers} answered</span></div><div className="qe-progress-track" role="progressbar" aria-label="Quiz progress" aria-valuemin={0} aria-valuemax={quiz.questions.length} aria-valuenow={completedAnswers}><i style={{ width: `${progressPercent(completedAnswers - 1, quiz.questions.length)}%` }}/></div>
          <nav className="qe-question-nav" aria-label="Question navigation">{quiz.questions.map((question, index) => <button type="button" key={question.attempt_id} className={`${active === index ? "active " : ""}${answers[question.attempt_id]?.trim() ? "answered" : ""}`} aria-current={active === index ? "step" : undefined} onClick={() => setActive(index)}>Q{index + 1}{answers[question.attempt_id]?.trim() ? " ✓" : ""}</button>)}</nav>
          <div className="qe-question"><span className="qe-question-type">{activeQuestion.type.replaceAll("_", " ")} · {activeQuestion.difficulty}</span><h3>{activeQuestion.prompt}</h3><QuestionInput question={activeQuestion} value={answers[activeQuestion.attempt_id] || ""} disabled={busy} onChange={value => setAnswers(current => ({ ...current, [activeQuestion.attempt_id]: value }))}/></div>
          <div className="qe-quiz-actions"><button className="qe-secondary" type="button" disabled={active === 0} onClick={() => setActive(index => index - 1)}>← Previous</button>{active < quiz.questions.length - 1 ? <button className="qe-primary" type="button" onClick={() => setActive(index => index + 1)}>Next question →</button> : !confirmSubmit ? <button className="qe-primary" type="button" disabled={completedAnswers !== quiz.questions.length || busy} onClick={() => setConfirmSubmit(true)}>{labels.submit}</button> : <div className="qe-confirm" role="group" aria-label="Confirm quiz submission"><span>{labels.confirm}</span><button className="qe-primary" type="button" disabled={busy} onClick={() => void submitQuiz()}>{busy ? "Submitting…" : "Confirm"}</button><button className="qe-secondary" type="button" onClick={() => setConfirmSubmit(false)}>Review</button></div>}</div>
          {completedAnswers < quiz.questions.length && active === quiz.questions.length - 1 && <p className="qe-hint">Answer each question before submitting.</p>}
        </section>}

        {results && <section className="qe-panel qe-results" aria-labelledby="qe-results-title"><div className="qe-result-hero"><span className="qe-eyebrow">{labels.score}</span><div className="qe-score">{results.score}<small> / {results.question_count}</small></div><h2 id="qe-results-title">{currentResultFeedback === "strong" ? labels.strong : currentResultFeedback === "building" ? labels.building : labels.review}</h2><p>{results.topic} · {results.difficulty} · {results.mastery_score}% topic score</p></div>
          <div className="qe-feedback-grid"><article><span className="qe-eyebrow">{labels.strength}</span><p>{results.score > 0 ? `${results.score} ${language === "telugu" ? "సరైన సమాధానాలు" : "correct answers"}` : labels.review}</p></article><article><span className="qe-eyebrow">{labels.reviewArea}</span><p>{incorrect.length ? incorrect.map(question => question.question_id).join(", ") : (language === "telugu" ? "ప్రస్తుతం బలహీన అంశాలు లేవు." : "No missed questions this time.")}</p></article></div>
          <div className="qe-explanations"><h3>Answer review / సమాధానాల వివరణ</h3>{results.questions.map(question => <article className={question.is_correct ? "qe-explanation correct" : "qe-explanation missed"} key={question.attempt_id}><div><strong>{question.is_correct ? "✓ Correct" : "↺ Review"}</strong><span>Question {question.position}</span></div><p>{question.prompt}</p><small>Your answer: {question.answer} · Answer: {question.correct_answer}</small><p>{question.explanation}</p></article>)}</div>
          {results.topic_recommendation && <p className="qe-recommendation"><strong>Next step:</strong> {results.topic_recommendation}</p>}
          <div className="qe-result-actions"><button type="button" className="qe-primary" onClick={() => { setResults(null); setQuiz(null); setAnswers({}); setError(""); }}>{labels.retry}</button><Link className="qe-secondary" to="/dashboard">Back to dashboard</Link></div>
        </section>}

        <section className="qe-panel qe-history"><div className="qe-panel-head"><div><span className="qe-eyebrow">YOUR LEARNING JOURNEY</span><h2>{labels.history}</h2></div><span className="qe-chip">{history.length} saved</span></div>
          {history.length === 0 ? <p className="qe-empty-text">{labels.empty}</p> : <div className="qe-history-list">{history.slice(0, 8).map(item => <button type="button" className="qe-history-row" key={item.quiz_id} disabled={!item.completed || busy} onClick={() => void openHistory(item)}><span><strong>{item.topic}</strong><small>{item.subject} · {new Date(item.issued_at).toLocaleDateString()}</small></span><span className="qe-history-score">{item.completed ? `${item.score}/${item.question_count}` : "In progress"}<small>{item.difficulty}</small></span></button>)}</div>}
        </section>
      </>}
    </div>
  </main>;
}
