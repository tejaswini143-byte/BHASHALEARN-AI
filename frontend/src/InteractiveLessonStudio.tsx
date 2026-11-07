import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { boardReducer, createBoardState, playbackReducer, sampleLessons, validateLessonPlan, type LessonObject, type LessonPlan, type PlaybackAction } from "./lessonEngine";
import "./interactive-lesson.css";

type Tool = "select" | "draw" | "erase" | "highlight" | "pan";
const COLORS: Record<string, string> = { cyan: "#50d9ef", purple: "#ac91ff", gold: "#ffd579", pink: "#ff87ca" };
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

function Shape({ item, active, focused, onPointerDown, onActivate }: { item: LessonObject; active: boolean; focused: boolean; onPointerDown: (id: string, event: React.PointerEvent<SVGElement>) => void; onActivate: (id: string) => void }) {
  const color = COLORS[item.color || "cyan"] || COLORS.cyan;
  const common = { "data-object-id": item.id, onPointerDown: (event: React.PointerEvent<SVGElement>) => onPointerDown(item.id, event), onClick: () => onActivate(item.id), className: `il-object${active ? " il-highlighted" : ""}${focused ? " il-focused" : ""}` };
  if (item.shape === "circle") return <g {...common} role="button" tabIndex={0} aria-label={`${item.text || "Circle"}: ${item.explanation || "Select object"}`}><circle cx={item.x} cy={item.y} r={(item.width || 70) / 2} fill={`${color}24`} stroke={color} strokeWidth="3"/><text x={item.x} y={item.y + 5} textAnchor="middle" className="il-shape-label">{item.text}</text></g>;
  if (item.shape === "triangle") return <g {...common} role="button" tabIndex={0} aria-label={`Triangle: ${item.explanation || "Select object"}`}><polygon points={`${item.x},${item.y + (item.height || 100)} ${item.x + (item.width || 120)},${item.y + (item.height || 100)} ${item.x + (item.width || 120)},${item.y}`} fill={`${color}16`} stroke={color} strokeWidth="4"/><path d={`M ${item.x + (item.width || 120) - 28} ${item.y + (item.height || 100)} v -25 h 25`} fill="none" stroke={color} strokeWidth="2"/><text x={item.x + (item.width || 120) / 2} y={item.y + (item.height || 100) + 28} textAnchor="middle" className="il-shape-label">{item.text}</text></g>;
  if (item.shape === "line") return <g {...common} role="button" tabIndex={0} aria-label={`${item.text || "Line"}: ${item.explanation || "Select object"}`}><line x1={item.x} y1={item.y} x2={item.x + (item.width || 65)} y2={item.y} stroke={color} strokeWidth="4" markerEnd="url(#il-arrow)"/><text x={item.x + (item.width || 65) / 2} y={item.y - 13} textAnchor="middle" className="il-small-label">{item.text}</text></g>;
  if (item.shape === "path") return <g {...common} role="button" tabIndex={0} aria-label="Student drawing" transform={`translate(${item.x} ${item.y})`}><polyline points={(item.points || []).map(point => `${point.x - item.x},${point.y - item.y}`).join(" ")} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"/></g>;
  const isText = item.shape === "text";
  return <g {...common} role="button" tabIndex={0} aria-label={`${item.text || "Label"}: ${item.explanation || "Select object"}`}><rect x={item.x} y={item.y} width={item.width || 180} height={item.height || 62} rx={isText ? 14 : 18} fill={isText ? "#111b39" : `${color}17`} stroke={color} strokeWidth="2"/><text x={item.x + (item.width || 180) / 2} y={item.y + (item.height || 62) / 2 + 5} textAnchor="middle" className={item.text && item.text.length > 20 ? "il-small-label" : "il-shape-label"}>{item.text}</text></g>;
}

export function InteractiveLessonStudio() {
  const [lessonId, setLessonId] = useState(sampleLessons[0].id);
  const lesson = useMemo(() => validateLessonPlan(sampleLessons.find(item => item.id === lessonId)!), [lessonId]);
  const [board, dispatch] = useReducer(boardReducer, lesson.objects, createBoardState);
  const [tool, setTool] = useState<Tool>("select");
  const [playback, dispatchPlaybackAction] = useReducer((state: { step: number; playing: boolean }, action: PlaybackAction) => playbackReducer(state, action, lesson.steps.length), { step: -1, playing: false });
  const { step, playing } = playback;
  const [speed, setSpeed] = useState(1000);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [selected, setSelected] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState("");
  const [fullScreen, setFullScreen] = useState(false);
  const [notice, setNotice] = useState("");
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ id: string; x: number; y: number; startX: number; startY: number } | null>(null);
  const panRef = useRef<{ x: number; y: number; startX: number; startY: number } | null>(null);
  const drawRef = useRef<string | null>(null);
  const allObjects = [...board.authored, ...board.student];
  const explanationObject = allObjects.find(item => item.id === board.focused) || allObjects.find(item => item.id === selected);
  const currentStep = step >= 0 ? lesson.steps[step] : null;

  function point(event: React.PointerEvent<SVGSVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    const factor = Math.min(rect.width / 1000, rect.height / 620);
    const originX = (rect.width - 1000 * factor) / 2;
    const originY = (rect.height - 620 * factor) / 2;
    return { x: clamp(((event.clientX - rect.left - originX) / factor - pan.x) / scale, 0, 1000), y: clamp(((event.clientY - rect.top - originY) / factor - pan.y) / scale, 0, 620) };
  }
  function act(command: LessonPlan["steps"][number]["commands"][number]) { dispatch({ type: "command", command }); }
  function applyStep(index: number, keepPlaying = false) {
    if (index < -1 || index >= lesson.steps.length) return;
    dispatchPlaybackAction({ type: "go", step: index, playing: keepPlaying });
    setNotice("");
    dispatch({ type: "replay", authored: lesson.objects });
    if (index >= 0) lesson.steps.slice(0, index + 1).forEach(item => item.commands.forEach(act));
  }
  useEffect(() => {
    dispatch({ type: "set-objects", authored: lesson.objects }); dispatchPlaybackAction("replay"); setSelected(null); setAnswer(""); setFeedback(""); setScale(1); setPan({ x: 0, y: 0 });
  }, [lesson]);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      if (step + 1 >= lesson.steps.length) dispatchPlaybackAction("pause");
      else applyStep(step + 1, true);
    }, speed);
    return () => window.clearTimeout(timer);
  }, [playing, step, speed, lesson]);
  useEffect(() => {
    const updateFullscreen = () => setFullScreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", updateFullscreen);
    return () => document.removeEventListener("fullscreenchange", updateFullscreen);
  }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); dispatch({ type: event.shiftKey ? "redo" : "undo", initial: lesson.objects }); }
      else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); dispatch({ type: "redo", initial: lesson.objects }); }
      else if (event.key === "Delete" && selected) dispatch({ type: "erase-object", id: selected });
      else if (selected && ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        const item = allObjects.find(value => value.id === selected);
        if (item) { dispatch({ type: "snapshot" }); dispatch({ type: "move-object", id: item.id, x: clamp(item.x + (event.key === "ArrowRight" ? 8 : event.key === "ArrowLeft" ? -8 : 0), 0, 950), y: clamp(item.y + (event.key === "ArrowDown" ? 8 : event.key === "ArrowUp" ? -8 : 0), 0, 570) }); }
      }
      else if (event.key === "ArrowRight") applyStep(Math.min(step + 1, lesson.steps.length - 1));
      else if (event.key === "ArrowLeft") applyStep(Math.max(-1, step - 1));
      else if (event.key === "Escape" && document.fullscreenElement) void document.exitFullscreen();
    };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [selected, step, lesson]);

  function onObjectDown(id: string, event: React.PointerEvent<SVGElement>) {
    if (tool === "draw" || tool === "pan") return;
    event.stopPropagation();
    const target = allObjects.find(item => item.id === id);
    if (tool === "erase") { dispatch({ type: "erase-object", id }); if (selected === id) setSelected(null); return; }
    if (tool === "highlight") { dispatch({ type: "highlight", id }); setSelected(id); return; }
    if (tool !== "select" || !target) return;
    const pos = point(event as unknown as React.PointerEvent<SVGSVGElement>);
    setSelected(id); dispatch({ type: "focus", id }); dispatch({ type: "snapshot" });
    dragRef.current = { id, x: target.x, y: target.y, startX: pos.x, startY: pos.y };
    event.currentTarget.ownerSVGElement?.setPointerCapture(event.pointerId);
  }
  function onObjectActivate(id: string) {
    if (tool === "select") { setSelected(id); dispatch({ type: "focus", id }); }
    else if (tool === "highlight") { setSelected(id); dispatch({ type: "highlight", id }); }
    else if (tool === "erase") { dispatch({ type: "erase-object", id }); if (selected === id) setSelected(null); }
  }
  function onBoardDown(event: React.PointerEvent<SVGSVGElement>) {
    const pos = point(event);
    if (tool === "draw") {
      const id = `student-drawing-${Date.now()}`; drawRef.current = id;
      dispatch({ type: "add-student", object: { id, shape: "path", x: pos.x, y: pos.y, points: [pos], color: "cyan", explanation: "Your drawing" } }); event.currentTarget.setPointerCapture(event.pointerId);
    } else if (tool === "pan" || event.button === 1) { panRef.current = { x: pan.x, y: pan.y, startX: event.clientX, startY: event.clientY }; event.currentTarget.setPointerCapture(event.pointerId); }
    else if (tool === "select") setSelected(null);
  }
  function onBoardMove(event: React.PointerEvent<SVGSVGElement>) {
    const pos = point(event);
    if (dragRef.current) { const drag = dragRef.current; dispatch({ type: "move-object", id: drag.id, x: clamp(drag.x + pos.x - drag.startX, 0, 950), y: clamp(drag.y + pos.y - drag.startY, 0, 570) }); }
    if (drawRef.current) { const item = board.student.find(value => value.id === drawRef.current); if (item) dispatch({ type: "update-student", id: item.id, update: { points: [...(item.points || []), pos] } }); }
    if (panRef.current) { const factor = Math.min(event.currentTarget.clientWidth / 1000, event.currentTarget.clientHeight / 620); setPan({ x: panRef.current.x + (event.clientX - panRef.current.startX) / factor / scale, y: panRef.current.y + (event.clientY - panRef.current.startY) / factor / scale }); }
  }
  function onBoardUp() { dragRef.current = null; drawRef.current = null; panRef.current = null; }
  function addShape(shape: "circle" | "rect" | "triangle" | "text") {
    const id = `student-${shape}-${Date.now()}`;
    const defaults = { id, shape, x: 410, y: 260, width: shape === "circle" ? 84 : 180, height: shape === "circle" ? 84 : shape === "triangle" ? 130 : 62, text: shape === "circle" ? "" : shape === "triangle" ? "" : shape === "text" ? "Type your label" : "", color: "purple", explanation: "Student-created object" } as LessonObject;
    if (shape === "text") { const text = window.prompt("Label text", "Type your label"); if (!text?.trim()) return; defaults.text = text.trim(); }
    dispatch({ type: "add-student", object: defaults }); setSelected(id); setTool("select");
  }
  function checkAnswer() { const correct = answer === lesson.exercise.answer; setFeedback(correct ? `✓ Correct. ${lesson.exercise.feedback}` : "Not quite yet. Try again and look at the highlighted idea."); }
  async function toggleFullscreen() {
    const target = document.querySelector(".il-shell");
    try { if (!document.fullscreenElement) await target?.requestFullscreen(); else await document.exitFullscreen(); setFullScreen(Boolean(document.fullscreenElement)); }
    catch { setNotice("Full-screen mode is unavailable in this browser."); }
  }
  const toolButtons: Array<[Tool, string, string]> = [["select", "↖", "Select and move"], ["draw", "✎", "Draw freely"], ["erase", "⌫", "Erase object"], ["highlight", "✦", "Highlight object"], ["pan", "✥", "Pan board"]];

  return <section className="il-shell" aria-label="Interactive lesson studio" onDoubleClick={event => { if ((event.target as HTMLElement).closest(".il-board")) void toggleFullscreen(); }}>
    <header className="il-top"><div><div className="il-brand">BHASHA<span>LEARN</span><i> · VISUAL STUDIO</i></div><h2>Learn by seeing<span>.</span></h2></div><div className="il-top-actions"><label>Lesson <select aria-label="Sample lesson" value={lessonId} onChange={event => setLessonId(event.target.value)}>{sampleLessons.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><button type="button" onClick={() => void toggleFullscreen()} aria-pressed={fullScreen}>⛶ {fullScreen ? "Exit full screen" : "Full screen"}</button></div></header>
    <div className="il-meta"><span className="il-kicker">{lesson.subject}</span><h3>{lesson.title}</h3><p>{lesson.intro}</p></div>
    <div className="il-toolbar" role="toolbar" aria-label="Smartboard tools">{toolButtons.map(([key, icon, label]) => <button type="button" key={key} aria-label={label} aria-pressed={tool === key} className={tool === key ? "il-tool-active" : ""} onClick={() => setTool(key)}><span aria-hidden="true">{icon}</span><small>{label}</small></button>)}<i/>{([["circle", "Add circle"], ["triangle", "Add triangle"], ["rect", "Add rectangle"], ["text", "Add label"]] as const).map(([shape, label]) => <button type="button" key={shape} aria-label={label} onClick={() => addShape(shape)}><span aria-hidden="true">{shape === "circle" ? "○" : shape === "triangle" ? "△" : shape === "rect" ? "▱" : "T"}</span><small>{label}</small></button>)}<i/><button type="button" aria-label="Undo" disabled={!board.undo.length} onClick={() => dispatch({ type: "undo", initial: lesson.objects })}>↶<small>Undo</small></button><button type="button" aria-label="Redo" disabled={!board.redo.length} onClick={() => dispatch({ type: "redo", initial: lesson.objects })}>↷<small>Redo</small></button><button type="button" aria-label="Reset board" onClick={() => { dispatch({ type: "reset", initial: lesson.objects }); dispatchPlaybackAction("replay"); setSelected(null); setNotice("Board reset. Your private drawings were cleared."); }}>⟳<small>Reset</small></button><i/><button type="button" aria-label="Zoom out" onClick={() => setScale(value => clamp(value - .15, .5, 2.5))}>−<small>Zoom out</small></button><span className="il-zoom" aria-live="polite">{Math.round(scale * 100)}%</span><button type="button" aria-label="Zoom in" onClick={() => setScale(value => clamp(value + .15, .5, 2.5))}>+<small>Zoom in</small></button><button type="button" aria-label="Reset zoom and pan" onClick={() => { setScale(1); setPan({ x: 0, y: 0 }); }}>⟲<small>Center</small></button></div>
    <div className="il-workspace"><section className="il-board-card" aria-label="Interactive smartboard"><div className="il-board-heading"><span className="il-kicker">SMARTBOARD · {tool.toUpperCase()}</span><span><i/> LIVE CANVAS</span></div><div className="il-board" onWheel={event => { if (event.ctrlKey) { event.preventDefault(); setScale(value => clamp(value + (event.deltaY < 0 ? .1 : -.1), .5, 2.5)); } }}><svg ref={svgRef} viewBox="0 0 1000 620" preserveAspectRatio="xMidYMid meet" role="application" aria-label="Interactive smartboard. Use the toolbar to draw, select, move, erase, and zoom." onPointerDown={onBoardDown} onPointerMove={onBoardMove} onPointerUp={onBoardUp} onPointerCancel={onBoardUp} onPointerLeave={onBoardUp}>
        <defs><pattern id="il-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M 32 0 L 0 0 0 32" fill="none" stroke="#83a4d4" strokeOpacity=".09" strokeWidth="1"/></pattern><marker id="il-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#ffd579"/></marker></defs><rect width="1000" height="620" fill="url(#il-grid)" pointerEvents="none"/><g transform={`translate(${pan.x} ${pan.y}) scale(${scale})`}>
          {board.authored.map(item => <Shape key={item.id} item={item} active={board.highlighted === item.id} focused={board.focused === item.id} onPointerDown={onObjectDown} onActivate={onObjectActivate}/>)}<g className="il-student-layer">{board.student.map(item => <Shape key={item.id} item={item} active={board.highlighted === item.id || selected === item.id} focused={board.focused === item.id} onPointerDown={onObjectDown} onActivate={onObjectActivate}/>)}</g>
        </g></svg></div><div className="il-board-footer"><span><b className="il-layer-dot"/> Lesson content <b className="il-layer-dot student"/> Your private marks</span><span>Draw · select · drag · erase · Ctrl + wheel to zoom</span></div></section>
      <aside className="il-side"><section className="il-card il-step-card"><div className="il-card-title"><span className="il-kicker">GUIDED EXPLANATION</span><span>{step < 0 ? "READY" : `STEP ${step + 1} / ${lesson.steps.length}`}</span></div><h4>{currentStep?.title || "Your smartboard is ready"}</h4><p>{currentStep?.explanation || "Press play to start the lesson, or explore the board on your own."}</p><div className="il-playback"><button type="button" aria-label="Previous lesson step" disabled={step < 0} onClick={() => applyStep(Math.max(-1, step - 1))}>← Previous</button><button type="button" className="il-play" aria-label={playing ? "Pause lesson" : "Play lesson"} onClick={() => { if (playing) dispatchPlaybackAction("pause"); else { if (step >= lesson.steps.length - 1) { dispatch({ type: "replay", authored: lesson.objects }); setSelected(null); } dispatchPlaybackAction("toggle"); } }}>{playing ? "Ⅱ Pause" : "▶ Play"}</button><button type="button" aria-label="Next lesson step" disabled={step >= lesson.steps.length - 1} onClick={() => applyStep(Math.min(lesson.steps.length - 1, step + 1))}>Next →</button></div><div className="il-progress"><div style={{ width: `${((step + 1) / lesson.steps.length) * 100}%` }}/></div><div className="il-step-count"><span>{step < 0 ? "Ready to begin" : `${step + 1} of ${lesson.steps.length} steps`}</span><label>Speed <select aria-label="Lesson playback speed" value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={1400}>Slow</option><option value={1000}>Normal</option><option value={600}>Fast</option></select></label></div></section>
        <section className="il-card il-context" aria-live="polite"><span className="il-kicker">{explanationObject ? "OBJECT EXPLORER" : "EXPLORE THE BOARD"}</span><h4>{explanationObject?.text || "Select a diagram"}</h4><p>{explanationObject?.explanation || "Click any shape, label, or diagram to see what it represents."}</p>{selected && <button type="button" className="il-remove" onClick={() => { dispatch({ type: "erase-object", id: selected }); setSelected(null); }}>Remove selected object</button>}</section>
        <section className="il-card il-exercise"><span className="il-kicker">QUICK CHECK</span><h4>{lesson.exercise.prompt}</h4><div className="il-choices">{lesson.exercise.choices.map(choice => <button type="button" key={choice} aria-pressed={answer === choice} className={answer === choice ? "il-choice-selected" : ""} onClick={() => { setAnswer(choice); setFeedback(""); }}>{choice}</button>)}</div><button type="button" className="il-check" disabled={!answer} onClick={checkAnswer}>Check answer</button>{feedback && <p className={feedback.startsWith("✓") ? "il-feedback correct" : "il-feedback"} role="status">{feedback}</p>}</section>
      </aside></div>
    {notice && <div className="il-notice" role="status">{notice}<button type="button" aria-label="Dismiss message" onClick={() => setNotice("")}>×</button></div>}<footer className="il-footnote">Built-in sample lesson · Your drawings stay in this browser session · Lesson plans use a validated, versioned integration contract</footer>
  </section>;
}
