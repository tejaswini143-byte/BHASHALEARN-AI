import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getToken, request } from "./auth";
import { getSharedSessionContext, sessionHeaders, type SharedSessionContext, type LearningLanguage } from "./sessionContext";
import { SessionModeNav } from "./SessionModeNav";
import "./visual.css";

type Tab = "Explanation" | "Animation" | "Code & Equations" | "Diagrams" | "Applications" | "Summary" | "Quiz";
type Lang = LearningLanguage;
type SessionSummary = { id: string; topic: string; language: Lang; created_at: string };
type VisualKey = "fractions-equivalent" | "dijkstra-shortest-path";
type TopicProgress = { topic: string; mastery_score: number | null; mastery_category: string; evidence_count: number; recommended_difficulty: string; teaching_strategy: string; reason: string; review_areas: string[] };
const visualTitles: Record<VisualKey,string> = { "fractions-equivalent": "Equivalent Fractions", "dijkstra-shortest-path": "Dijkstra's Shortest Path" };
type NodeId = "A" | "B" | "C" | "D" | "E" | "F";
type Edge = { a: NodeId; b: NodeId; w: number };
const tabs: Tab[] = ["Explanation", "Animation", "Code & Equations", "Diagrams", "Applications", "Summary", "Quiz"];
const positions: Record<NodeId, [number, number]> = { A:[90,180], B:[245,65], C:[245,285], D:[420,95], E:[420,280], F:[580,180] };
const edges: Edge[] = [{a:"A",b:"B",w:4},{a:"A",b:"C",w:2},{a:"B",b:"C",w:1},{a:"B",b:"D",w:5},{a:"C",b:"D",w:8},{a:"C",b:"E",w:10},{a:"D",b:"E",w:2},{a:"D",b:"F",w:6},{a:"E",b:"F",w:3}];
const nodes = Object.keys(positions) as NodeId[];
const copy = { english: { intro:"Discover how Dijkstra's algorithm finds the shortest path through a weighted graph.", step:"Explore each decision, from selecting the nearest unvisited node to updating distances.", quiz:"Which node is visited first after A when A is the starting node?", correct:"C", explanation:"C has distance 2 from A, which is less than B's distance 4." }, telugu: { intro:"బరువులు ఉన్న గ్రాఫ్‌లో డైక్స్ట్రా అల్గారిథమ్ అతి తక్కువ దూరం గల మార్గాన్ని ఎలా కనుగొంటుందో తెలుసుకోండి.", step:"సమీప నోడ్‌ను ఎంచుకోవడం నుంచి దూరాలను నవీకరించడం వరకు ప్రతి దశను పరిశీలించండి.", quiz:"A ప్రారంభ నోడ్ అయితే, A తర్వాత మొదట సందర్శించే నోడ్ ఏది?", correct:"C", explanation:"A నుంచి C దూరం 2, B దూరం 4. కాబట్టి C ముందుగా వస్తుంది." } };
function solve(start: NodeId) {
  const distances = Object.fromEntries(nodes.map(n=>[n,Infinity])) as Record<NodeId,number>;
  const previous: Partial<Record<NodeId,NodeId>> = {};
  const visited: NodeId[] = [];
  const frames: { visited: NodeId[]; current: NodeId | null; distances: Record<NodeId,number>; previous: Partial<Record<NodeId,NodeId>>; description: string }[] = [];
  distances[start] = 0;
  frames.push({visited:[],current:null,distances:{...distances},previous:{},description:`Initialize distance to ${start} as 0; all others are ∞.`});
  while(visited.length<nodes.length) {
    const next = nodes.filter(n=>!visited.includes(n)).sort((a,b)=>distances[a]-distances[b])[0];
    if (!next || !Number.isFinite(distances[next])) break;
    visited.push(next);
    for (const edge of edges) {
      const neighbor = edge.a === next ? edge.b : edge.b === next ? edge.a : null;
      if (!neighbor || visited.includes(neighbor)) continue;
      if (distances[next]+edge.w < distances[neighbor]) { distances[neighbor]=distances[next]+edge.w; previous[neighbor]=next; }
    }
    frames.push({visited:[...visited],current:next,distances:{...distances},previous:{...previous},description:`Visit ${next}; relax its neighboring edges and update tentative distances.`});
  }
  return frames;
}
function pathTo(previous: Partial<Record<NodeId,NodeId>>, start: NodeId, end: NodeId) {
  const path: NodeId[] = [end];
  while(path[0] !== start && previous[path[0]]) path.unshift(previous[path[0]]!);
  return path[0] === start ? path : [];
}
function Graph({ visited, current, path }: { visited: NodeId[]; current: NodeId | null; path: NodeId[] }) {
  return <svg className="vs-graph" viewBox="0 0 670 360" role="img" aria-label="Six-node weighted graph showing visited nodes and highlighted shortest path">
    <defs><linearGradient id="vs-path-gradient" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#40d9ee"/><stop offset="1" stopColor="#a28aff"/></linearGradient></defs>
    {edges.map(({a,b,w})=>{const [x1,y1]=positions[a], [x2,y2]=positions[b];const active=path.some((node,i)=>i>0 && ((node===a&&path[i-1]===b)||(node===b&&path[i-1]===a)));return <g key={a+b}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke={active?"url(#vs-path-gradient)":"#65749d"} strokeWidth={active?6:2.5} strokeLinecap="round"/><rect x={(x1+x2)/2-13} y={(y1+y2)/2-13} width="26" height="26" rx="8" fill="#1a2548"/><text x={(x1+x2)/2} y={(y1+y2)/2+5} textAnchor="middle" fontSize="14" fill="#e4edff">{w}</text></g>})}
    {nodes.map(node=>{const [x,y]=positions[node];const isCurrent=current===node;const inPath=path.includes(node);return <g key={node}><circle cx={x} cy={y} r="26" fill={isCurrent?"#7658e8":inPath?"#237b9b":visited.includes(node)?"#34487a":"#202d55"} stroke={inPath?"#6ee9ff":isCurrent?"#c0a5ff":"#7785b7"} strokeWidth={inPath?4:2}/><text x={x} y={y+6} textAnchor="middle" fill="white" fontSize="19" fontWeight="700">{node}</text></g>})}
  </svg>;
}
export function VisualStudio() {
  const navigate=useNavigate();
  const [params,setParams]=useSearchParams();
  const [sessions,setSessions]=useState<SessionSummary[]>([]);
  const [sessionId,setSessionId]=useState("");
  const [context,setContext]=useState<SharedSessionContext|null>(null);
  const [learningProgress,setLearningProgress]=useState<TopicProgress|null>(null);
  const [visualKey,setVisualKey]=useState<VisualKey>("dijkstra-shortest-path");
  const [loading,setLoading]=useState(true);
  const [sessionError,setSessionError]=useState("");
  const [notice,setNotice]=useState("");
  const [saving,setSaving]=useState(false);
  const [tab,setTab]=useState<Tab>("Animation");
  const [language,setLanguage]=useState<Lang>("mixed");
  const [start,setStart]=useState<NodeId>("A");
  const [end,setEnd]=useState<NodeId>("F");
  const [step,setStep]=useState(0);
  const [playing,setPlaying]=useState(false);
  const [answer,setAnswer]=useState("");
  const [revealed,setRevealed]=useState(false);
  const [light,setLight]=useState(false);
  const [speed,setSpeed]=useState(1100);
  const frames=useMemo(()=>solve(start),[start]);
  const frame=frames[Math.min(step,frames.length-1)];
  const path=pathTo(frame.previous,start,end);
  const done=frame.visited.includes(end);
  const displayLanguage=language==="mixed"?"english":language;
useEffect(()=>{let alive=true;const token=getToken();if(!token){navigate("/login",{replace:true});return;}Promise.all([request<SessionSummary[]>("/sessions?limit=100",{headers:{Authorization:"Bearer "+token}}),request<{preferred_language:Lang}>("/students/me/preferences",{headers:{Authorization:"Bearer "+token}})]).then(([list,prefs])=>{if(!alive)return;setSessions(list);setLanguage(prefs.preferred_language);const requested=params.get("session");const chosen=requested?list.find(item=>item.id===requested):list[0];if(requested&&!chosen){setSessionError("This session is unavailable or you do not have access to it.");return;}if(chosen)setSessionId(chosen.id);else setSessionError("Create a learning session in Chat before opening a visual lesson.");}).catch(cause=>{if(alive)setSessionError(cause instanceof Error?cause.message:"Unable to load learning sessions.");}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};},[navigate]);
  useEffect(()=>{if(!sessionId)return;setParams({session:sessionId});let active=true;setContext(null);getSharedSessionContext(sessionId).then(async value=>{if(!active)return;setContext(value);setLanguage(value.preferred_language);const saved=value.visual_lesson;if(saved){setVisualKey(saved.visual_key as VisualKey);if(saved.start_node)setStart(saved.start_node as NodeId);if(saved.end_node)setEnd(saved.end_node as NodeId);}else{const key:VisualKey=/fraction/i.test(value.topic)?"fractions-equivalent":"dijkstra-shortest-path";setVisualKey(key);setStart("A");setEnd("F");const body=key==="dijkstra-shortest-path"?{visual_key:key,start_node:"A",end_node:"F"}:{visual_key:key};await request(`/sessions/${encodeURIComponent(sessionId)}/visual-context`,{method:"PUT",headers:sessionHeaders(),body:JSON.stringify(body)});const updated=await getSharedSessionContext(sessionId);if(active)setContext(updated);}}).catch(cause=>{if(active)setSessionError(cause instanceof Error?cause.message:"Unable to load session context.");});return()=>{active=false;};},[sessionId,setParams]);
  useEffect(()=>{let active=true;setLearningProgress(null);if(!sessionId)return;request<{topics:TopicProgress[];recent_evidence:unknown[] }>("/progress/summary",{headers:sessionHeaders()}).then(summary=>{if(!active)return;const topic=context?.topic||sessions.find(item=>item.id===sessionId)?.topic||"";const normalized=topic.trim().replace(/\s+/g," ").toLocaleLowerCase();setLearningProgress(summary.topics.find(item=>item.topic.trim().replace(/\s+/g," ").toLocaleLowerCase()===normalized)||null);}).catch(()=>{if(active)setLearningProgress(null);});return()=>{active=false;};},[sessionId,context?.topic,sessions]);
  useEffect(()=>{if(!playing)return;const timer=window.setInterval(()=>setStep(i=>{if(i>=frames.length-1){setPlaying(false);return i;}return i+1;}),speed);return ()=>window.clearInterval(timer);},[playing,frames.length,speed]);
  useEffect(()=>{setStep(0);setPlaying(false);},[start,end]);
async function persistVisual(key:VisualKey,nextStart=start,nextEnd=end){if(!sessionId)return;const body=key==="dijkstra-shortest-path"?{visual_key:key,start_node:nextStart,end_node:nextEnd}:{visual_key:key};setSaving(true);try{await request(`/sessions/${encodeURIComponent(sessionId)}/visual-context`,{method:"PUT",headers:sessionHeaders(),body:JSON.stringify(body)});setContext(await getSharedSessionContext(sessionId));}catch(cause){setNotice(cause instanceof Error?cause.message:"Could not save visual state.");}finally{setSaving(false);}}
  async function updateLanguage(value:Lang){const previous=language;setLanguage(value);try{await request("/students/me/preferences",{method:"PUT",headers:sessionHeaders(),body:JSON.stringify({preferred_language:value,learning_level:context?.learning_level||"beginner",learning_goal:context?.learning_goal||null})});if(sessionId)setContext(await getSharedSessionContext(sessionId));}catch(cause){setLanguage(previous);setNotice(cause instanceof Error?cause.message:"Could not update language preference.");}}
  function switchTab(value: Tab){setTab(value);if(value!=="Animation")setPlaying(false);}
  if(loading)return <main className="auth-screen"><p className="auth-wait">Loading learning session...</p></main>; if(sessionError&&!context)return <main className="auth-screen"><div className="cl-fatal"><h2>Visual lesson unavailable</h2><p role="alert">{sessionError}</p><Link to="/dashboard">Return to dashboard</Link><Link to="/classroom">Open Chat</Link></div></main>; return <div className={light?"vs-app vs-light":"vs-app"}>
    <aside className="vs-sidebar"><Link to="/dashboard" className="vs-brand">✦ BHASHA<span>LEARN</span></Link><Link to="/dashboard" className="vs-back">← Student dashboard</Link><div className="vs-sidebar-title">LEARNING SESSION</div><label className="vs-session-select">Session<select value={sessionId} onChange={event=>{setSessionId(event.target.value);setParams({session:event.target.value});}}>{sessions.map(item=><option key={item.id} value={item.id}>{item.topic}</option>)}</select></label><label className="vs-session-select">Visual lesson<select value={visualKey} disabled={saving} onChange={event=>{const value=event.target.value as VisualKey;setVisualKey(value);setStart("A");setEnd("F");void persistVisual(value,"A","F");}}><option value="fractions-equivalent">Equivalent Fractions</option><option value="dijkstra-shortest-path">Dijkstra's Shortest Path</option></select></label><div className="vs-sidebar-note">Topic: {context?.topic}<br/>Visual selection is saved to this learning session.</div></aside>
    <main className="vs-main"><header className="vs-top"><div><span className="vs-eyebrow">✦ INTERACTIVE VISUAL STUDIO</span><h1>Learn by <span>seeing.</span></h1></div><div className="vs-top-actions"><label>Language <select value={language} onChange={e=>void updateLanguage(e.target.value as Lang)}><option value="english">English</option><option value="telugu">తెలుగు</option><option value="mixed">Telugu + English</option></select></label><button onClick={()=>setLight(v=>!v)}>{light?"☾ Dark mode":"☀ Light mode"}</button></div><SessionModeNav sessionId={sessionId} active="visual"/></header>
    {notice&&<p role="status" className="vs-notice">{notice}</p>}<div className="vs-content">{learningProgress&&<aside className="vs-learning-guidance" aria-label="Adaptive learning guidance"><strong>Learning guidance · {learningProgress.mastery_category.replaceAll("_"," ")}</strong><span>{learningProgress.evidence_count ? `${learningProgress.evidence_count} scored checks · ${learningProgress.recommended_difficulty} guidance` : `Not assessed · ${learningProgress.recommended_difficulty} starting level`}</span><p>{learningProgress.reason}{learningProgress.review_areas[0]?` ${learningProgress.review_areas[0]}`:""}</p><small>Viewing or changing this visual lesson does not change your progress.</small></aside>}<div className="vs-lesson-heading"><div><span className="vs-eyebrow">ALGORITHMS / GRAPHS</span><h2>{context?.visual_lesson?.title||visualTitles[visualKey]}</h2><p>{visualKey==="fractions-equivalent"?"Compare equal portions of a whole across different partitions.":copy[displayLanguage].intro}</p></div><span className="vs-level">INTERACTIVE DEMO</span></div>
    {visualKey==="fractions-equivalent"?<section className="vs-card vs-fractions"><h3>Equivalent fractions</h3><p>Three equal bars show that 1/2 = 2/4 = 4/8.</p>{[[2,1],[4,2],[8,4]].map(([parts,shaded])=><div className="vs-fraction-row" key={parts}><strong>{shaded}/{parts}</strong><div>{Array.from({length:parts},(_,index)=><span key={index} className={index<shaded?"vs-fraction-shaded":""}/>)}</div></div>)}</section>:<><div className="vs-tabs" role="tablist" aria-label="Lesson sections">{tabs.map(value=><button role="tab" aria-selected={tab===value} key={value} className={tab===value?"vs-tab-active":""} onClick={()=>switchTab(value)}>{value}</button>)}</div>
    {tab==="Animation"||tab==="Diagrams"?<div className="vs-columns"><section className="vs-card vs-canvas"><div className="vs-card-head"><div><span className="vs-eyebrow">LIVE VISUALIZATION</span><h3>Weighted graph</h3></div><span className="vs-legend">● Path &nbsp; ◉ Visited</span></div><div className="vs-graph-wrap"><Graph visited={frame.visited} current={frame.current} path={path}/></div><div className="vs-controls"><label>Start <select value={start} onChange={e=>{const value=e.target.value as NodeId;setStart(value);void persistVisual(visualKey,value,end);}}>{nodes.map(n=><option key={n}>{n}</option>)}</select></label><label>End <select value={end} onChange={e=>{const value=e.target.value as NodeId;setEnd(value);void persistVisual(visualKey,start,value);}}>{nodes.map(n=><option key={n}>{n}</option>)}</select></label><button disabled={step===0} onClick={()=>{setPlaying(false);setStep(i=>i-1);}}>← Prev</button><button className="vs-play" onClick={()=>{if(step===frames.length-1)setStep(0);setPlaying(v=>!v);}}>{playing?"Ⅱ Pause":"▶ Play"}</button><button disabled={step>=frames.length-1} onClick={()=>{setPlaying(false);setStep(i=>i+1);}}>Next →</button></div><div className="vs-progress"><div style={{width:`${step/(frames.length-1)*100}%`}}/></div><div className="vs-step-count">Step {step+1} of {frames.length} <label>Speed <select value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={1600}>Slow</option><option value={1100}>Normal</option><option value={550}>Fast</option></select></label></div></section>
    <aside className="vs-card vs-inspector"><span className="vs-eyebrow">STEP-BY-STEP EXPLANATION</span><h3>{frame.current?`Visiting node ${frame.current}`:"Initialization"}</h3><p>{frame.description}</p><p>{copy[displayLanguage].step}</p><div className="vs-distance-title">Tentative distances from {start}</div><div className="vs-distance-grid">{nodes.map(n=><div key={n}><strong>{n}</strong><span>{Number.isFinite(frame.distances[n])?frame.distances[n]:"∞"}</span></div>)}</div><div className="vs-result"><strong>Shortest path to {end}</strong><p>{done?(path.join(" → ") + " · Total weight: " + frame.distances[end]):"Advance the animation until the destination is visited."}</p></div></aside></div>:
    <section className="vs-card vs-article">{tab==="Explanation"?<><h3>How Dijkstra's algorithm works</h3><p>{copy[displayLanguage].intro}</p><ol><li>Set the starting node's distance to zero and every other distance to infinity.</li><li>Visit the unvisited node with the smallest tentative distance.</li><li>Check its neighbors and replace their distances when a shorter route is found.</li><li>Repeat until the destination is visited or no reachable nodes remain.</li></ol><p>All edge weights in this example are non-negative, as required by Dijkstra's algorithm.</p></>:
    tab==="Code & Equations"?<><h3>Algorithm and equations</h3><p>Relax an edge from node u to v with weight w:</p><div className="vs-equation">dist[v] = min(dist[v], dist[u] + w)</div><pre>{`dist[start] = 0
for all other nodes: dist[node] = Infinity
while unvisited reachable nodes remain:
    u = unvisited node with smallest dist[u]
    mark u visited
    for each unvisited neighbor v:
        if dist[u] + weight(u,v) < dist[v]:
            dist[v] = dist[u] + weight(u,v)
            previous[v] = u`}</pre><p>With a binary heap, typical complexity is O((V + E) log V).</p></>:
    tab==="Applications"?<><h3>Where shortest paths matter</h3><div className="vs-tiles"><div><strong>🗺️ Navigation</strong><p>Find efficient road routes when edges represent travel distance or time.</p></div><div><strong>🌐 Networking</strong><p>Explore lowest-cost routes between network nodes.</p></div><div><strong>🤖 Robotics</strong><p>Plan routes through mapped spaces with non-negative costs.</p></div></div></>:
    tab==="Summary"?<><h3>What you learned</h3><p>Dijkstra's algorithm grows a set of nodes whose shortest distances are known. Each step selects the unvisited node with the smallest tentative distance and relaxes neighboring edges.</p><p>Use the Animation tab to test different start and end nodes. The graph's edge weights stay fixed, and the shortest path updates from your selected start.</p></>:
    <><h3>Knowledge check</h3><p>{copy[displayLanguage].quiz}</p><div className="vs-quiz-choices">{["B","C","D","F"].map(n=><label key={n}><input type="radio" name="vs-quiz" value={n} checked={answer===n} onChange={()=>{setAnswer(n);setRevealed(false);}}/> Node {n}</label>)}</div><button className="vs-quiz-submit" disabled={!answer} onClick={()=>setRevealed(true)}>Check answer</button>{revealed&&<p className={answer===copy[displayLanguage].correct?"vs-correct":"vs-incorrect"} role="status">{answer===copy[displayLanguage].correct?"✓ Correct!":"Not quite. Try again."} {copy[displayLanguage].explanation}</p>}<small>This quiz is a local practice activity; no score is submitted to your account.</small></>}</section>}
    </>}<div className="vs-footer">Lesson 01 · Built-in Dijkstra demo · Interactive learning workspace · More lesson types planned for later integration</div></div></main></div>;
}
