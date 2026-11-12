import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import { getSharedSessionContext } from "./sessionContext";
import { SessionModeNav } from "./SessionModeNav";
import { PracticeAssessment } from "./PracticeAssessment";
import { classroomUrl, isEducationalDoubt } from "./classroomHandoff";
import "./chat.css";

type Session={id:string;topic:string;language:string;created_at:string};
type Message={id:string;role:"user"|"assistant";content:string;created_at:string};
type TutorReply={reply:string;session_id:string;language:string;learning_level:string};
const tokenHeaders=()=>({Authorization:"Bearer "+getToken()});
const prompts=["Explain in Telugu and English","Give me a real-life example","Create a short practice exercise","Quiz me on this topic"];
function formatDate(date:string){return new Date(date).toLocaleDateString(undefined,{month:"short",day:"numeric"});}
export function AdvancedChat(){
  const navigate=useNavigate();
  const [params,setParams]=useSearchParams();
  const [student,setStudent]=useState<Student|null>(null);
  const [sessions,setSessions]=useState<Session[]>([]);
  const [selected,setSelected]=useState("");
  const [messages,setMessages]=useState<Message[]>([]);
  const [draft,setDraft]=useState("");
  const [topic,setTopic]=useState("");
  const [search,setSearch]=useState("");
  const [loading,setLoading]=useState(true);
  const [historyLoading,setHistoryLoading]=useState(false);
  const [busy,setBusy]=useState(false);
  const [creating,setCreating]=useState(false);
  const [error,setError]=useState("");
  const [menuOpen,setMenuOpen]=useState(false);
  const [classroomQuestion,setClassroomQuestion]=useState("");`n  const [teacherPicker,setTeacherPicker]=useState(false);
  const bottom=useRef<HTMLDivElement>(null);
  const requestId=useRef(0);
  const activeSession=useRef("");
  const signOut=useCallback(()=>{clearToken();navigate("/login",{replace:true});},[navigate]);
  const fail=useCallback((cause:unknown)=>{if(cause instanceof ApiError&&cause.status===401){signOut();return;}setError(cause instanceof Error?cause.message:"Request failed.");},[signOut]);
  useEffect(()=>{let alive=true;const token=getToken();if(!token){signOut();return;}Promise.all([getCurrentStudent(token),request<Session[]>("/sessions?limit=100",{headers:{Authorization:"Bearer "+token}})]).then(([profile,list])=>{if(!alive)return;setStudent(profile);setSessions(list);const requested=params.get("session");if(requested&&list.some(item=>item.id===requested))setSelected(requested);else if(!requested&&list.length)setSelected(list[0].id);else if(requested)setError("That learning session is unavailable or you do not have access.");}).catch(cause=>{if(alive)fail(cause);}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};},[fail,signOut]);
  useEffect(()=>{activeSession.current=selected;const id=++requestId.current;setMessages([]);if(!selected){setHistoryLoading(false);return;}setHistoryLoading(true);getSharedSessionContext(selected).then(context=>{if(id===requestId.current)setMessages(context.messages);}).catch(cause=>{if(id===requestId.current)fail(cause);}).finally(()=>{if(id===requestId.current)setHistoryLoading(false);});},[selected,fail]);
  useEffect(()=>{bottom.current?.scrollIntoView({block:"end",behavior:"smooth"});},[messages,busy]);
  async function createChat(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!topic.trim()||creating||busy)return;setCreating(true);setError("");try{const session=await request<Session>("/sessions",{method:"POST",headers:tokenHeaders(),body:JSON.stringify({topic:topic.trim(),language:"mixed"})});setSessions(items=>[session,...items]);setSelected(session.id);setParams({session:session.id});setTopic("");setMenuOpen(false);}catch(cause){fail(cause);}finally{setCreating(false);}}
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!selected || !message || busy || historyLoading) return;
    const id = selected;
    setBusy(true); setError(""); setDraft(""); setClassroomQuestion(""); setTeacherPicker(false);
    const optimistic: Message = { id: "temp-" + Date.now(), role: "user", content: message, created_at: new Date().toISOString() };
    setMessages(items => [...items, optimistic]);
    try {
      const reply = await request<TutorReply>(`/tutor/sessions/${encodeURIComponent(id)}/chat`, { method: "POST", headers: tokenHeaders(), body: JSON.stringify({ message }) });
      if (activeSession.current === id) {
        setMessages(items => [...items, { id: "reply-" + Date.now(), role: "assistant", content: reply.reply, created_at: new Date().toISOString() }]);
        if (isEducationalDoubt(message)) setClassroomQuestion(message);
      }
      try {
        const saved = await request<Message[]>(`/sessions/${encodeURIComponent(id)}/messages?limit=500`, { headers: tokenHeaders() });
        if (activeSession.current === id) setMessages(saved);
      } catch { /* Keep the confirmed reply visible when history refresh fails. */ }
    } catch (cause) {
      setMessages(items => items.filter(item => item.id !== optimistic.id));
      setDraft(message); fail(cause);
    } finally { setBusy(false); }
  }  const filtered=sessions.filter(s=>s.topic.toLowerCase().includes(search.toLowerCase()));
  const current=sessions.find(s=>s.id===selected);
  if(loading)return <main className="auth-screen"><p className="auth-wait">Opening your chat workspace…</p></main>;
  if(!student)return <main className="auth-screen"><div className="cl-fatal"><h2>Unable to load chat</h2><p role="alert">{error}</p><button onClick={()=>window.location.reload()}>Retry</button><button onClick={signOut}>Sign out</button></div></main>;
  return <div className="ac-app"><aside className={menuOpen?"ac-sidebar ac-sidebar-open":"ac-sidebar"}><Link className="ac-brand" to="/dashboard">✦ BHASHA<span>LEARN</span> AI</Link><Link className="ac-home" to="/dashboard">← Back to dashboard</Link><div className="ac-side-heading">NEW CONVERSATION</div><form className="ac-new" onSubmit={createChat}><input aria-label="New conversation topic" maxLength={200} placeholder="What do you want to learn?" value={topic} onChange={e=>setTopic(e.target.value)}/><button disabled={!topic.trim()||creating||busy}>{creating?"Creating…":"＋ New chat"}</button></form><div className="ac-side-heading">YOUR CONVERSATIONS</div><label className="ac-search">⌕ <input placeholder="Search conversations" aria-label="Search conversations" value={search} onChange={e=>setSearch(e.target.value)}/></label><nav className="ac-conversations" aria-label="Saved conversations">{filtered.map(s=><button key={s.id} disabled={busy} className={selected===s.id?"ac-selected":""} onClick={()=>{setSelected(s.id);setParams({session:s.id});setError("");setMenuOpen(false);}}><span>▤</span><span><strong>{s.topic}</strong><small>{formatDate(s.created_at)} · {s.language}</small></span></button>)}{!filtered.length&&<p>{sessions.length?"No matching conversations.":"Create a topic to begin chatting."}</p>}</nav><div className="ac-side-bottom"><span className="ac-avatar">{student.display_name.charAt(0).toUpperCase()}</span><div><strong>{student.display_name}</strong><small>Learning workspace</small></div><button onClick={signOut} aria-label="Sign out">↪</button></div></aside>
  <main className="ac-main"><header className="ac-header"><div><button className="ac-menu" aria-label="Toggle conversations" onClick={()=>setMenuOpen(v=>!v)}>☰</button><span className="ac-eyebrow">✦ BILINGUAL AI LEARNING</span><h1>{current?.topic||"New conversation"}</h1></div><SessionModeNav sessionId={selected} active="chat"/></header><section className="ac-thread" aria-label="Conversation messages">{historyLoading?<div className="ac-welcome"><p>Loading conversation…</p></div>:messages.length?messages.map(m=><article key={m.id} className={m.role==="user"?"ac-message ac-user":"ac-message ac-assistant"}><div className="ac-message-avatar">{m.role==="user"?"YOU":"✦"}</div><div><div className="ac-message-label">{m.role==="user"?"You":"BHASHALEARN Tutor"}</div><div className="ac-bubble">{m.content}</div>{m.role==="assistant"&&<button className="ac-copy" onClick={()=>navigator.clipboard?.writeText(m.content)} aria-label="Copy tutor reply">⧉ Copy</button>}</div></article>):<div className="ac-welcome"><span className="ac-welcome-icon">✦</span><span className="ac-eyebrow">YOUR PERSONAL AI LEARNING COMPANION</span><h2>What will you <span>discover today?</span></h2><p>Ask questions in Telugu, English, or both. Explore examples, practice conversations, and learn at your own pace.</p><div className="ac-prompts">{prompts.map(p=><button key={p} disabled={!selected} onClick={()=>setDraft(p)}>{p} ↗</button>)}</div>{!selected&&<p>Create a new conversation using the sidebar to begin.</p>}</div>}{classroomQuestion&&<section className="ac-classroom-invite" aria-label="Interactive classroom invitation"><p>Would you like me to explain this in our interactive classroom?</p><div className="ac-classroom-actions"><button type="button" className="ac-classroom-yes" onClick={()=>setTeacherPicker(true)}>Yes, explain in classroom</button><button type="button" className="ac-classroom-no" onClick={()=>{setClassroomQuestion("");setTeacherPicker(false);}}>Continue in chat</button></div>{teacherPicker&&<div className="ac-teacher-choices"><button type="button" onClick={()=>navigate(classroomUrl(selected,classroomQuestion,"realistic"))}>Human Teacher</button><button type="button" onClick={()=>navigate(classroomUrl(selected,classroomQuestion,"holographic"))}>Hologram Teacher</button></div>}</section>}{busy&&<div className="ac-thinking">✦ Your tutor is thinking…</div>}<div ref={bottom}/></section><footer className="ac-footer">{error&&<p className="ac-error" role="alert">{error}</p>}<form onSubmit={send}><textarea rows={2} maxLength={4000} aria-label="Message to AI tutor" placeholder={selected?"Ask anything about your topic…":"Create or select a conversation first"} disabled={!selected||busy||historyLoading} value={draft} onChange={e=>setDraft(e.target.value)}/><button disabled={!selected||!draft.trim()||busy||historyLoading}>{busy?"Thinking…":"Send ↗"}</button></form><p>AI responses can make mistakes. Check important information. Messages are saved to your learning session.</p></footer><PracticeAssessment sessionId={selected}/></main></div>;
}
