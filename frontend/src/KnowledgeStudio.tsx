import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, getToken, request } from "./auth";
import "./knowledge-studio.css";
import "./knowledge-topic.css";

type DocumentItem = { id: string; original_filename: string; processing_status: string; page_count: number | null };
type Citation = { citation_id: string; document_id: string; document_title: string; page_number: number };
type ChatMessage = { role: "user" | "assistant"; content: string; citations?: Citation[]; grounded?: boolean };
type QuizQuestion = { question: string; choices: string[]; correct_index: number; explanation: string; citation_ids: string[] };
type LearningReply = { mode: string; content: string; questions: QuizQuestion[]; citations: Citation[]; grounded: boolean };
const auth = () => ({ Authorization: "Bearer " + getToken() });
const modes = ["summary", "concepts", "flashcards", "practice", "quiz"] as const;

export function KnowledgeStudio() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [ready, setReady] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [language, setLanguage] = useState("mixed");
  const [topic, setTopic] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<(typeof modes)[number] | "">("");
  const [material, setMaterial] = useState<LearningReply | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    if (!getToken()) { navigate("/login", { replace: true }); return; }
    (async () => {
      try {
        const items = await request<DocumentItem[]>("/documents?limit=100", { headers: auth() });
        const statuses = await Promise.all(items.filter(item => item.processing_status === "processed").map(async item => {
          try { const state = await request<{ status: string }>(`/documents/${encodeURIComponent(item.id)}/index-status`, { headers: auth() }); return state.status === "ready" ? item.id : null; }
          catch { return null; }
        }));
        if (!active) return;
        setDocuments(items); setReady(statuses.filter((id): id is string => id !== null));
      } catch (cause) {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) navigate("/login", { replace: true });
        else setError(cause instanceof Error ? cause.message : "Could not load your documents.");
      } finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [navigate]);

  const selectedNames = useMemo(() => documents.filter(item => selected.includes(item.id)).map(item => item.original_filename).join(", "), [documents, selected]);
  function toggle(id: string) { setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id].slice(0, 10)); }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy || !selected.length) return;
    setBusy(true); setError(""); setQuestion(""); setMode("");
    const prior = messages;
    setMessages(current => [...current, { role: "user", content: text }]);
    try {
      const reply = await request<{ answer: string; citations: Citation[]; grounded: boolean }>("/knowledge/ask", {
        method: "POST", headers: { ...auth(), "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: selected, question: text, language, history: prior.slice(-8).map(({ role, content }) => ({ role, content })) }),
      });
      setMessages(current => [...current, { role: "assistant", content: reply.answer, citations: reply.citations, grounded: reply.grounded }]);
    } catch (cause) { setMessages(prior); setQuestion(text); setError(cause instanceof Error ? cause.message : "Could not answer from your documents."); }
    finally { setBusy(false); }
  }

  async function generate(modeValue: (typeof modes)[number]) {
    if (!selected.length || busy) return;
    setBusy(true); setError(""); setMode(modeValue); setMaterial(null); setAnswers({}); setChecked(false);
    try {
      const result = await request<LearningReply>("/knowledge/learning", {
        method: "POST", headers: { ...auth(), "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: selected, mode: modeValue, topic: topic.trim(), language }),
      });
      setMaterial(result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create study material."); }
    finally { setBusy(false); }
  }

  return <main className="knowledge-shell">
    <header className="knowledge-header"><Link to="/documents" className="knowledge-back">? Documents</Link><span className="knowledge-kicker">PRIVATE, SOURCE GROUNDED STUDY</span><h1>Knowledge Studio</h1><p>Ask questions and build practice material from the PDFs you choose.</p></header>
    <div className="knowledge-layout">
      <aside className="knowledge-card knowledge-library" aria-label="Select study documents"><div className="knowledge-card-title"><span className="knowledge-kicker">YOUR LIBRARY</span><h2>Choose PDFs</h2><p>Select up to 10 indexed documents.</p></div>
        {loading ? <p role="status">Loading your documents?</p> : documents.length === 0 ? <div className="knowledge-empty"><h3>No PDFs yet</h3><p>Upload your study material to get started.</p><Link to="/documents">Upload a PDF</Link></div> : <div className="knowledge-doc-list">{documents.map(item => <label className="knowledge-doc" key={item.id}><input type="checkbox" checked={selected.includes(item.id)} disabled={!ready.includes(item.id) && !selected.includes(item.id)} onChange={() => toggle(item.id)} /><span><strong>{item.original_filename}</strong><small>{ready.includes(item.id) ? `${item.page_count ?? 0} pages ? Ready to study` : item.processing_status === "text_extraction_unavailable" ? "Scanned PDF ? OCR unavailable" : item.processing_status === "processed" ? "Index this document first" : "Text unavailable"}</small></span></label>)}</div>}
        <label className="knowledge-language">Explanation language<select value={language} onChange={event => setLanguage(event.target.value)}><option value="mixed">?????? + English</option><option value="telugu">??????</option><option value="english">English</option></select></label>
        <label className="knowledge-language">Chapter or section (optional)<input className="knowledge-topic-input" value={topic} maxLength={200} onChange={event => setTopic(event.target.value)} placeholder="For example: Fractions" /></label>
      </aside>
      <section className="knowledge-main">
        <section className="knowledge-card knowledge-chat" aria-labelledby="knowledge-chat-title"><div className="knowledge-card-title"><span className="knowledge-kicker">DOCUMENT Q&amp;A</span><h2 id="knowledge-chat-title">Ask your material</h2><p>{selected.length ? `Using: ${selectedNames}` : "Select at least one indexed PDF to begin."}</p></div>
          <div className="knowledge-transcript" aria-live="polite">{messages.length === 0 ? <div className="knowledge-empty"><span>?</span><h3>Your study conversation starts here</h3><p>Answers will show the document and page used. If your PDFs do not support an answer, the tutor will say so.</p></div> : messages.map((message, index) => <article className={`knowledge-message ${message.role}`} key={`${index}-${message.role}`}><b>{message.role === "user" ? "You" : "Study tutor"}</b><p>{message.content}</p>{message.role === "assistant" && (!message.grounded || !message.citations?.length) && <small className="knowledge-uncertain">No supporting page citation was found for this answer.</small>}{message.citations?.map(cite => <Link className="knowledge-citation" key={cite.citation_id} to={`/documents/${encodeURIComponent(cite.document_id)}?page=${cite.page_number}#page-${cite.page_number}`}>{cite.citation_id} ? {cite.document_title} ? page {cite.page_number}</Link>)}</article>)}{busy && !mode && <p className="knowledge-pending" role="status">Searching selected pages?</p>}</div>
          <form className="knowledge-ask" onSubmit={ask}><label className="sr-only" htmlFor="knowledge-question">Ask a question about your selected documents</label><input id="knowledge-question" value={question} onChange={event => setQuestion(event.target.value)} maxLength={1200} placeholder="Ask a question or follow up?" disabled={!selected.length || busy} /><button type="submit" disabled={!selected.length || !question.trim() || busy}>{busy && !mode ? "Thinking?" : "Ask"}</button></form>
        </section>
        <section className="knowledge-card knowledge-learning" aria-labelledby="knowledge-learning-title"><div className="knowledge-card-title"><span className="knowledge-kicker">TURN READING INTO PRACTICE</span><h2 id="knowledge-learning-title">Build study material</h2><p>Generated content is marked as source grounded only when it has valid page references.</p></div><div className="knowledge-actions">{modes.map(item => <button type="button" key={item} onClick={() => void generate(item)} disabled={!selected.length || busy} aria-pressed={mode === item}>{busy && mode === item ? "Creating?" : item === "concepts" ? "Key concepts" : item === "practice" ? "Practice questions" : item[0].toUpperCase() + item.slice(1)}</button>)}</div>
          {material && <div className="knowledge-material" aria-live="polite"><h3>{mode === "quiz" ? "Document quiz" : mode === "concepts" ? "Key concepts" : mode?.[0].toUpperCase() + mode?.slice(1)}</h3>{mode === "quiz" ? <><p>{material.content}</p>{material.questions.map((item, qi) => <fieldset className="knowledge-question" key={qi} disabled={checked}><legend>{qi + 1}. {item.question}</legend>{item.choices.map((choice, ci) => <label key={ci}><input type="radio" name={`quiz-${qi}`} checked={answers[qi] === ci} onChange={() => setAnswers(current => ({ ...current, [qi]: ci }))} />{choice}</label>)}{checked && <p className={answers[qi] === item.correct_index ? "answer-correct" : "answer-review"}>{answers[qi] === item.correct_index ? "Correct. " : `Review: ${item.choices[item.correct_index]}. `}{item.explanation}</p>}</fieldset>)}{material.questions.length > 0 && !checked && <button type="button" className="knowledge-check" disabled={Object.keys(answers).length !== material.questions.length} onClick={() => setChecked(true)}>Check answers</button>}</> : <pre>{material.content}</pre>}{material.citations.map(cite => <Link className="knowledge-citation" key={cite.citation_id} to={`/documents/${encodeURIComponent(cite.document_id)}?page=${cite.page_number}#page-${cite.page_number}`}>{cite.citation_id} ? {cite.document_title} ? page {cite.page_number}</Link>)}{!material.grounded && <p className="knowledge-uncertain">This material could not be verified against a sufficiently relevant page.</p>}</div>}
        </section>
        {error && <p className="knowledge-error" role="alert">{error}</p>}
      </section>
    </div>
  </main>;
}
