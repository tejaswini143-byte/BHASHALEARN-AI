import { useState } from "react";
import { saveFutureSeekerReflection, describeFutureSeekerError } from "./futureSeekerApi";
import { Link } from "react-router-dom";
import { careerScenarios, chooseScenarioOption, demonstratedSkills, isSimulationComplete, startSimulation, type CareerId, type SimulationState } from "./futureMeModel";
import "./future-me.css";

export function FutureMeSimulator() {
  const [simulation, setSimulation] = useState<SimulationState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");
  const [savedReflectionId, setSavedReflectionId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ outcome: string; explanation: string; nextPrompt?: string } | null>(null);
  const career = simulation ? careerScenarios.find(item => item.id === simulation.careerId)! : null;
  const complete = simulation ? isSimulationComplete(simulation) : false;
  const step = career && simulation ? career.steps[simulation.stepIndex] : null;

  function begin(id: CareerId) { setSimulation(startSimulation(id)); setFeedback(null); setSaveStatus(""); setSavedReflectionId(null); }
  async function saveReflection() {
    if (!simulation || !isSimulationComplete(simulation) || saving || savedReflectionId) return;
    setSaving(true); setSaveStatus("");
    try {
      const saved = await saveFutureSeekerReflection(simulation.careerId, simulation.choices.length, demonstratedSkills(simulation));
      setSavedReflectionId(saved.id);
      setSaveStatus("Reflection saved to your account. It does not verify your skills.");
    } catch (error) { setSaveStatus(describeFutureSeekerError(error)); }
    finally { setSaving(false); }
  }
  function choose(choiceId: string) {
    if (!simulation || !career) return;
    const choice = career.steps[simulation.stepIndex]?.choices.find(item => item.id === choiceId);
    if (!choice) return;
    setFeedback({ outcome: choice.outcome, explanation: choice.explanation, nextPrompt: choice.nextPrompt });
    setSimulation(chooseScenarioOption(simulation, choiceId));
  }

  return <main className="fm-shell">
    <header className="fm-topbar"><Link className="fm-brand" to="/" aria-label="BHASHALEARN AI home"><span>✦</span> BHASHA<span>LEARN</span><small> AI</small></Link><Link className="fm-back" to="/dashboard">← Learning dashboard</Link></header>
    <div className="fm-content">
      <section className="fm-hero" aria-labelledby="fm-heading"><div><span className="fm-eyebrow">✦ EXPLORE WHAT YOU COULD LEARN</span><h1 id="fm-heading">Meet a possible <span>future you.</span></h1><p>Step into a few made-up workday moments. Make choices, see what happens, and notice the skills you use along the way.</p></div><div className="fm-orbit" aria-hidden="true"><i/><i/><b>✧</b></div></section>
      <aside className="fm-disclaimer" role="note"><span aria-hidden="true">ⓘ</span><p><strong>Just an illustration.</strong> These scenarios are created for learning and reflection. They do not predict your future, measure your potential, or tell you which career to choose.</p></aside>

      {!career && <section className="fm-career-section" aria-labelledby="fm-careers-heading"><div className="fm-section-title"><div><span className="fm-eyebrow">CHOOSE A SCENARIO</span><h2 id="fm-careers-heading">Where should we visit?</h2></div><span className="fm-local-tag">LOCAL LEARNING SIMULATIONS</span></div><div className="fm-career-grid">{careerScenarios.map(item => <button className={`fm-career-card fm-${item.color}`} type="button" key={item.id} onClick={() => begin(item.id)}><span className="fm-career-icon" aria-hidden="true">{item.icon}</span><span className="fm-card-label">CAREER SCENARIO</span><strong>{item.title}</strong><span className="fm-card-summary">{item.summary}</span><span className="fm-card-action">Explore scenario <b aria-hidden="true">↗</b></span></button>)}</div></section>}

      {career && simulation && <section className="fm-simulation" aria-labelledby="fm-scenario-title">
        <div className="fm-sim-heading"><div><button type="button" className="fm-text-button" onClick={() => { setSimulation(null); setFeedback(null); setSaveStatus(""); setSavedReflectionId(null); }}>← All careers</button><span className="fm-eyebrow">ILLUSTRATIVE WORKPLACE SCENARIO</span><h2 id="fm-scenario-title">{career.title}<span> / </span><small>{career.workplace}</small></h2></div><span className="fm-step-pill">{complete ? "COMPLETE" : `MOMENT ${simulation.stepIndex + 1} OF ${career.steps.length}`}</span></div>
        <div className="fm-progress" role="progressbar" aria-label="Scenario progress" aria-valuemin={0} aria-valuemax={career.steps.length} aria-valuenow={simulation.choices.length}><span style={{ width: `${simulation.choices.length / career.steps.length * 100}%` }} /></div>
        {!complete && step && <div className="fm-scene-grid"><article className="fm-scene-card"><div className={`fm-scene-art fm-${career.color}`} aria-hidden="true"><span>{career.icon}</span><i/><i/><b>SIMULATION · {String(simulation.stepIndex + 1).padStart(2, "0")}</b></div><span className="fm-eyebrow">THE MOMENT</span><p>{step.setting}</p></article><section className="fm-decision-card" aria-labelledby="fm-prompt"><span className="fm-eyebrow">YOUR DECISION</span><h3 id="fm-prompt">{step.prompt}</h3><div className="fm-choice-list">{step.choices.map((choice, index) => <button key={choice.id} type="button" className="fm-choice" onClick={() => choose(choice.id)}><span className="fm-choice-key" aria-hidden="true">{String.fromCharCode(65 + index)}</span><span>{choice.label}</span><b aria-hidden="true">→</b></button>)}</div>{feedback && <div className="fm-feedback" role="status" aria-live="polite"><span className="fm-eyebrow">WHAT HAPPENS NEXT</span><p className="fm-outcome">{feedback.outcome}</p><p>{feedback.explanation}</p>{feedback.nextPrompt && <p className="fm-next-prompt">{feedback.nextPrompt}</p>}</div>}</section></div>}
        {complete && <div className="fm-complete" aria-labelledby="fm-complete-title"><div className="fm-complete-mark" aria-hidden="true">✓</div><span className="fm-eyebrow">SCENARIO COMPLETE</span><h3 id="fm-complete-title">You explored {career.title.toLowerCase()}.</h3><p>Your choices are one possible way through this fictional scenario. Different choices can lead to different conversations and outcomes.</p><section className="fm-summary-block" aria-labelledby="fm-path-title"><h4 id="fm-path-title">Your path through the scenario</h4><ol className="fm-path-list" aria-label="Your path through the scenario">{simulation.choices.map((choice, index) => <li key={`${index}-${choice.id}`}><strong>{choice.outcome}</strong><span>{choice.explanation}</span></li>)}</ol></section><section className="fm-summary-block" aria-labelledby="fm-skills-title"><h4 id="fm-skills-title">Skills you practiced</h4><div className="fm-skill-list">{demonstratedSkills(simulation).map(skill => <span key={skill}>{skill}</span>)}</div></section><section className="fm-summary-block" aria-labelledby="fm-next-title"><h4 id="fm-next-title">Ideas for what to learn next</h4><ul>{career.nextSteps.map(item => <li key={item}>{item}</li>)}</ul></section><div className="fm-save-reflection"><p>Optional: save this illustrative reflection to your account. It is not a skill assessment or career prediction.</p><button type="button" className="fm-primary-action" disabled={saving || Boolean(savedReflectionId)} onClick={saveReflection}>{saving ? "Saving…" : savedReflectionId ? "Saved to account" : "Save reflection to my account"}</button>{saveStatus && <p role="status" aria-live="polite">{saveStatus}</p>}<Link to="/career">Explore your learning roadmap</Link></div><div className="fm-complete-actions"><button className="fm-primary-action" onClick={() => begin(career.id)}>Replay this scenario</button><button className="fm-secondary-action" onClick={() => { setSimulation(null); setFeedback(null); }}>Explore another career</button></div></div>}
      </section>}
      <footer className="fm-footer"><span>BHASHALEARN AI · FUTURE ME SIMULATOR</span><span>Made for curiosity, reflection, and learning.</span></footer>
    </div>
  </main>;
}
