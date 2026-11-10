import { useEffect, useRef, useState } from "react";
import { getToken } from "./auth";
import type { PersonalizedLessonResponse } from "./personalizedTeaching";

type LessonStep = { title: string; content: string; kind: "objective" | "teaching" | "example" | "practice" | "next" };
type Props = {
  sessionId: string;
  language: string;
  result: PersonalizedLessonResponse;
  onAskAboutStep: (question: string) => void;
  onUnauthorized: () => void;
};

function buildSteps(result: PersonalizedLessonResponse): LessonStep[] {
  const plan = result.plan;
  return [
    { title: "Today's objective", content: plan.learning_objective, kind: "objective" },
    { title: "How we will learn", content: plan.explanation_strategy, kind: "teaching" },
    ...plan.examples.map((content, index) => ({ title: "Worked example " + (index + 1), content, kind: "example" as const })),
    ...plan.understanding_checks.map((content, index) => ({ title: "Check your understanding " + (index + 1), content, kind: "practice" as const })),
    { title: "Your next step", content: plan.suggested_next_activity, kind: "next" },
  ];
}

export function GuidedLessonPlayer({ sessionId, language, result, onAskAboutStep, onUnauthorized }: Props) {
  const steps = buildSteps(result);
  const [index, setIndex] = useState(0);
  const [mode, setMode] = useState<"idle" | "loading" | "playing" | "paused" | "finished" | "error">("idle");
  const [message, setMessage] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);
  const audioCache = useRef(new Map<number, string>());
  const requestRef = useRef<AbortController | null>(null);
  const step = steps[index];

  useEffect(() => {
    setIndex(0);
    setMode("idle");
    setMessage("");
    requestRef.current?.abort();
    requestRef.current = null;
    audioRef.current?.pause();
    audioCache.current.forEach(url => URL.revokeObjectURL(url));
    audioCache.current.clear();
    return () => {
      requestRef.current?.abort();
      audioRef.current?.pause();
      audioCache.current.forEach(url => URL.revokeObjectURL(url));
      audioCache.current.clear();
    };
  }, [sessionId, result]);

  async function speakStep(stepIndex: number) {
    const selectedStep = steps[stepIndex];
    if (!selectedStep) return;
    const audio = audioRef.current;
    if (!audio) return;
    setIndex(stepIndex);
    setMode("loading");
    setMessage("Generating this step with Gnani Timbre…");
    audio.pause();
    requestRef.current?.abort();
    const cached = audioCache.current.get(stepIndex);
    try {
      let url = cached;
      if (!url) {
        const token = getToken();
        if (!token) { onUnauthorized(); return; }
        const controller = new AbortController();
        requestRef.current = controller;
        const response = await fetch("/api/v1/voice/sessions/" + encodeURIComponent(sessionId) + "/speech", {
          method: "POST",
          headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
          body: JSON.stringify({ text: selectedStep.content, language }),
          signal: controller.signal,
        });
        if (!response.ok) {
          if (response.status === 401) { onUnauthorized(); return; }
          const body = await response.json().catch(() => null) as { detail?: unknown } | null;
          throw new Error(typeof body?.detail === "string" ? body.detail : "Speech request failed (" + response.status + ").");
        }
        url = URL.createObjectURL(await response.blob());
        audioCache.current.set(stepIndex, url);
      }
      if (requestRef.current?.signal.aborted) return;
      audio.src = url;
      audio.currentTime = 0;
      await audio.play();
      setMode("playing");
      setMessage("The board is showing the same step being spoken.");
    } catch (cause) {
      if (requestRef.current?.signal.aborted) return;
      setMode("error");
      setMessage(cause instanceof Error ? "Speech is unavailable. The written lesson remains available. " + cause.message : "Speech is unavailable. The written lesson remains available.");
    } finally {
      requestRef.current = null;
    }
  }

  async function continueLesson() {
    const audio = audioRef.current;
    if (audio?.src && audio.paused && audio.currentTime < audio.duration) {
      try { await audio.play(); setMode("playing"); setMessage("Continuing this lesson step."); }
      catch { setMode("error"); setMessage("Playback could not continue. Use Repeat step to try again."); }
      return;
    }
    await speakStep(index);
  }

  function pauseLesson() {
    requestRef.current?.abort();
    audioRef.current?.pause();
    setMode("paused");
    setMessage("Lesson paused. Ask your question in the tutor chat, then continue when ready.");
  }

  function nextStep() {
    const next = Math.min(index + 1, steps.length - 1);
    if (next === index) { setMode("finished"); setMessage("You reached the end of this lesson. Review a step or ask a follow-up."); return; }
    void speakStep(next);
  }

  function askAboutStep() {
    pauseLesson();
    onAskAboutStep("Please explain this lesson step more clearly: " + step.title + ". Current step: " + step.content);
  }

  return <section className="cl-guided" aria-labelledby="cl-guided-title">
    <div className="cl-guided-header">
      <div><span className="cl-personalized-kicker">SYNCHRONIZED LESSON</span><h3 id="cl-guided-title">Teach this lesson step by step</h3></div>
      <span className={result.plan.fallback ? "cl-guided-source cl-guided-fallback" : "cl-guided-source"}>{result.plan.fallback ? "DETERMINISTIC PLAN" : result.plan.grounded ? "GEMINI · DOCUMENT GROUNDED" : "GEMINI LESSON"}</span>
    </div>
    <article className="cl-guided-board" aria-live="polite" aria-label="Live teaching board">
      <div><span>BOARD · STEP {index + 1} OF {steps.length}</span><small>{step.kind.toUpperCase()}</small></div>
      <h4>{step.title}</h4>
      <p>{step.content}</p>
      {result.citations.length > 0 && <footer>Sources: {result.citations.map(source => source.document_title + " · p. " + source.page_number).join(" · ")}</footer>}
    </article>
    <audio ref={audioRef} onEnded={() => { if (mode === "playing") { setMode("finished"); setMessage("Step complete. Continue to the next explanation when ready."); } }} />
    <div className="cl-guided-controls" aria-label="Lesson playback controls">
      {mode === "idle" || mode === "finished" || mode === "error"
        ? <button onClick={() => void speakStep(index)}>{index === 0 ? "Start lesson" : "Speak this step"}</button>
        : mode === "playing" || mode === "loading"
          ? <button onClick={pauseLesson}>Pause</button>
          : <button onClick={() => void continueLesson()}>Continue</button>}
      <button onClick={() => void speakStep(index)} disabled={mode === "loading"}>Repeat step</button>
      <button onClick={nextStep} disabled={mode === "loading" || index >= steps.length - 1}>Next step</button>
      <button onClick={askAboutStep} disabled={mode === "loading"}>Ask about this step</button>
    </div>
    <p className={"cl-guided-status cl-guided-status-" + mode} role="status">{message || "Start the lesson to hear each board step with Gnani Timbre."}</p>
  </section>;
}
