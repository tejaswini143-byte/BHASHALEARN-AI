import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, type Student } from "./auth";
import { createMemory, deleteMemory, listMemories, updateMemory, type LearningMemory } from "./memoryApi";
import "./memories.css";

export function MemoriesPage() {
  const navigate = useNavigate();
  const [student, setStudent] = useState<Student | null>(null);
  const [memories, setMemories] = useState<LearningMemory[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [topic, setTopic] = useState("");
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) { signOut(); return; }
    setLoading(true); setError("");
    try {
      const [profile, items] = await Promise.all([getCurrentStudent(token), listMemories()]);
      setStudent(profile); setMemories(items);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
      setError(cause instanceof Error ? cause.message : "Could not load your learning memories.");
    } finally { setLoading(false); }
  }, [signOut]);

  useEffect(() => { void load(); }, [load]);

  function startEdit(memory: LearningMemory) {
    setEditing(memory.id); setTopic(memory.topic); setNote(memory.note); setError(""); setNotice("");
  }
  function resetForm() { setEditing(null); setTopic(""); setNote(""); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || !topic.trim() || !note.trim()) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const value = { topic: topic.trim(), note: note.trim() };
      if (editing) {
        const updated = await updateMemory(editing, value);
        setMemories(items => items.map(item => item.id === updated.id ? updated : item));
        setNotice("Memory updated.");
      } else {
        const created = await createMemory(value);
        setMemories(items => [created, ...items]);
        setNotice("Memory saved.");
      }
      resetForm();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
      setError(cause instanceof Error ? cause.message : "Could not save this memory.");
    } finally { setSaving(false); }
  }

  async function remove(memory: LearningMemory) {
    if (!window.confirm(`Delete the memory for “${memory.topic}”? This cannot be undone.`)) return;
    setError(""); setNotice("");
    try {
      await deleteMemory(memory.id);
      setMemories(items => items.filter(item => item.id !== memory.id));
      if (editing === memory.id) resetForm();
      setNotice("Memory deleted.");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
      setError(cause instanceof Error ? cause.message : "Could not delete this memory.");
    }
  }

  return <main className="memory-page">
    <header className="memory-top"><Link className="memory-brand" to="/dashboard">✦ BHASHA<span>LEARN</span> AI</Link><nav aria-label="Student navigation"><Link to="/dashboard">Dashboard</Link><Link to="/classroom">AI Classroom</Link><button onClick={signOut}>Sign out</button></nav></header>
    <div className="memory-content">
      <Link className="memory-back" to="/dashboard">← Dashboard</Link>
      <section className="memory-intro"><span className="memory-eyebrow">YOUR PERSONAL LEARNING CONTEXT</span><h1>Learning memories</h1><p>Save helpful context for your tutor, like what you are practicing or which explanations work for you. {student ? `These memories belong to ${student.display_name}.` : ""}</p></section>
      <div className="memory-columns">
        <section className="memory-form-card" aria-labelledby="memory-form-title"><span className="memory-eyebrow">{editing ? "MAKE A CORRECTION" : "SAVE A HELPFUL NOTE"}</span><h2 id="memory-form-title">{editing ? "Edit memory" : "Add a memory"}</h2><form onSubmit={submit}><label htmlFor="memory-topic">Topic</label><input id="memory-topic" required maxLength={200} value={topic} onChange={event => setTopic(event.target.value)} placeholder="e.g. Fractions"/><label htmlFor="memory-note">What should your tutor remember?</label><textarea id="memory-note" required maxLength={2000} rows={5} value={note} onChange={event => setNote(event.target.value)} placeholder="e.g. Show me a visual example before introducing the formula."/><div className="memory-form-actions"><button className="memory-primary" disabled={saving || !topic.trim() || !note.trim()}>{saving ? "Saving…" : editing ? "Save correction" : "Save memory"}</button>{editing && <button type="button" className="memory-secondary" onClick={resetForm}>Cancel</button>}</div></form></section>
        <section className="memory-list-card" aria-labelledby="memory-list-title"><div className="memory-list-heading"><div><span className="memory-eyebrow">PRIVATE TO YOUR ACCOUNT</span><h2 id="memory-list-title">Saved memories <span>{memories.length}</span></h2></div><button className="memory-refresh" onClick={() => void load()} disabled={loading}>Refresh</button></div>
          {error && <p className="memory-error" role="alert">{error} <button onClick={() => void load()}>Try again</button></p>}
          {notice && <p className="memory-success" role="status">{notice}</p>}
          {loading ? <p className="memory-state" role="status">Loading your learning memories…</p> : memories.length === 0 ? <div className="memory-empty"><span>✧</span><h3>No memories yet</h3><p>Save a learning preference or reminder and your tutor can use it in future lessons.</p></div> : <ul className="memory-list">{memories.map(memory => <li className="memory-item" key={memory.id}><div className="memory-item-top"><h3>{memory.topic}</h3><time dateTime={memory.created_at}>{new Date(memory.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</time></div><p>{memory.note}</p><div className="memory-item-actions"><button onClick={() => startEdit(memory)}>Correct</button><button className="memory-delete" onClick={() => void remove(memory)}>Delete</button></div></li>)}</ul>}
        </section>
      </div>
    </div>
  </main>;
}
