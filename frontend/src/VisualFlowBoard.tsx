import { useCallback, useEffect, useMemo, useState, type FormEvent, type MouseEvent } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { VisualLesson } from "./visualLessonsModel";
import { getToken, request } from "./auth";
import "./visual-flow.css";

type Props = {
  lesson: VisualLesson;
  activeStep: number;
  language: "en" | "te";
  onStepChange: (step: number) => void;
  onReset: () => void;
  sessionId: string;
};

function lessonNodes(lesson: VisualLesson, language: "en" | "te", activeStep: number): Node[] {
  const nodes: Node[] = [{
    id: "topic",
    position: { x: 300, y: 0 },
    data: { label: `${lesson.subject[language]} · ${lesson.topic[language]}` },
    type: "input",
    className: "vl-flow-topic",
  }];
  lesson.steps.forEach((step, index) => nodes.push({
    id: `step-${index}`,
    position: { x: 90 + (index % 3) * 270, y: 150 + Math.floor(index / 3) * 160 },
    data: { label: `${index + 1}. ${step.title[language]}` },
    className: index === activeStep ? "vl-flow-step vl-flow-active" : "vl-flow-step",
  }));
  lesson.objectives.forEach((objective, index) => nodes.push({
    id: `objective-${index}`,
    position: { x: 170 + index * 300, y: 430 },
    data: { label: `${language === "en" ? "Goal" : "లక్ష్యం"}: ${objective[language]}` },
    type: "output",
    className: "vl-flow-goal",
  }));
  return nodes;
}

function lessonEdges(lesson: VisualLesson): Edge[] {
  const edges: Edge[] = lesson.steps.map((_step, index) => ({
    id: `topic-step-${index}`,
    source: "topic",
    target: `step-${index}`,
    animated: true,
  }));
  lesson.objectives.forEach((_objective, index) => {
    const lastStep = Math.max(0, lesson.steps.length - 1);
    edges.push({ id: `step-objective-${index}`, source: `step-${lastStep}`, target: `objective-${index}` });
  });
  return edges;
}

export function VisualFlowBoard({ lesson, activeStep, language, onStepChange, onReset, sessionId }: Props) {
  const initialNodes = useMemo(() => lessonNodes(lesson, language, activeStep), [lesson, language, activeStep]);
  const initialEdges = useMemo(() => lessonEdges(lesson), [lesson]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedStep, setSelectedStep] = useState(activeStep);
  const [question, setQuestion] = useState("");
  const [aiReply, setAiReply] = useState("");
  const [aiError, setAiError] = useState("");
  const [askingAi, setAskingAi] = useState(false);

  useEffect(() => {
    setNodes(lessonNodes(lesson, language, activeStep));
    setEdges(lessonEdges(lesson));
    setSelectedStep(activeStep);
  }, [lesson, language, setNodes, setEdges]);
  useEffect(() => {
    setNodes(items => items.map(node => node.id.startsWith("step-")
      ? { ...node, className: Number(node.id.slice(5)) === activeStep ? "vl-flow-step vl-flow-active" : "vl-flow-step" }
      : node));
    setSelectedStep(activeStep);
  }, [activeStep, setNodes]);

  const onNodeClick = useCallback((_event: MouseEvent, node: Node) => {
    if (node.id.startsWith("step-")) {
      const index = Number(node.id.slice(5));
      setSelectedStep(index);
      onStepChange(index);
    }
  }, [onStepChange]);

  const current = lesson.steps[selectedStep];
  async function askTeacher(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = question.trim();
    const token = getToken();
    if (!prompt || !token || !sessionId || !current) return;
    setAskingAi(true);
    setAiError("");
    try {
      const result = await request<{ reply: string }>(`/tutor/sessions/${encodeURIComponent(sessionId)}/chat`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          language: language === "te" ? "telugu" : "english",
          message: `Visual lesson: ${lesson.title.en} (${lesson.title.te}). Topic: ${lesson.topic.en}. Current step ${selectedStep + 1}: ${current.title.en}. Step explanation: ${current.explanation.en}. Student question: ${prompt}. Answer in the requested language and explain this current step clearly.`,
        }),
      });
      setAiReply(result.reply);
      setQuestion("");
    } catch (error) {
      setAiError(error instanceof Error ? error.message : "The AI teacher could not answer right now.");
    } finally { setAskingAi(false); }
  }
  return <section className="vl-flow-card" aria-label={language === "en" ? "Interactive lesson concept map" : "ఇంటరాక్టివ్ పాఠ భావ పటం"}>
    <div className="vl-flow-heading">
      <div><span className="vl-eyebrow">{language === "en" ? "INTERACTIVE SMARTBOARD" : "ఇంటరాక్టివ్ స్మార్ట్‌బోర్డ్"}</span><h2>{language === "en" ? "Explore the lesson map" : "పాఠ భావ పటాన్ని చూడండి"}</h2></div>
      <button type="button" onClick={onReset}>{language === "en" ? "Reset and replay" : "మళ్లీ ప్రారంభించు"}</button>
    </div>
    <div className="vl-flow-canvas" role="region" aria-label={language === "en" ? "Draggable lesson diagram. Select a step node for its explanation." : "కదిలించగల పాఠ రేఖాచిత్రం. వివరణ కోసం దశను ఎంచుకోండి."}>
      <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={onNodeClick} fitView minZoom={0.35} maxZoom={1.8} nodesConnectable={false} aria-label="Lesson concept map">
        <Background gap={22} size={1} />
        <MiniMap pannable zoomable />
        <Controls />
      </ReactFlow>
    </div>
    <nav className="vl-flow-step-list" aria-label={language === "en" ? "Lesson steps" : "పాఠ దశలు"}>
      {lesson.steps.map((step, index) => <button key={`${lesson.id}-${index}`} type="button" aria-current={selectedStep === index ? "step" : undefined} onClick={() => { setSelectedStep(index); onStepChange(index); }}>
        {index + 1}. {step.title[language]}
      </button>)}
    </nav>
    {current && <div className="vl-flow-explanation" aria-live="polite"><strong>{current.title[language]}</strong><p>{current.explanation[language]}</p></div>}
    <form className="vl-flow-ask" onSubmit={event => void askTeacher(event)}>
      <label htmlFor="vl-flow-question">{language === "en" ? "Ask about this lesson" : "ఈ పాఠం గురించి అడగండి"}</label>
      <div><input id="vl-flow-question" value={question} onChange={event => setQuestion(event.target.value)} maxLength={1000} placeholder={language === "en" ? "What would you like the AI teacher to explain?" : "AI ఉపాధ్యాయుడిని ఏమి వివరించమంటారు?"}/><button type="submit" disabled={askingAi || !question.trim() || !sessionId}>{askingAi ? (language === "en" ? "Thinking…" : "ఆలోచిస్తోంది…") : (language === "en" ? "Ask teacher" : "ఉపాధ్యాయుడిని అడుగు")}</button></div>
      {aiError && <p role="alert">{aiError}</p>}{aiReply && <p className="vl-flow-ai-reply" role="status" aria-live="polite">{aiReply}</p>}
    </form>
  </section>;
}
