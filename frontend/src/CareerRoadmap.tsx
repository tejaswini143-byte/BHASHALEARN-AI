import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ApiError, getToken, request } from "./auth";
import { CareerRoadmap as Roadmap, gapLabel, percentComplete } from "./careerModel";
import "./career-roadmap.css";
import "./career-study.css";
import { CareerRoadmapGraph } from "./CareerRoadmapGraph";

type Direction = { career_key: string; title: string; title_te?: string; required_skills: string[] };
type ResumeSuggestion = { skill_key: string; proficiency: string; evidence: string };
type ResumeProfile = { document_id: string; filename: string; skills: ResumeSuggestion[]; experience_summary: string; field_of_study?: string | null; status: string };
type Goal = { id: string; career_key: string; career_title: string; career_title_te?: string; custom_goal?: string | null; target_date?: string | null; education_level: string; field_of_study?: string | null; experience_summary?: string | null; resume_profile?: ResumeProfile | null; interests: string[]; constraints?: string[]; weekly_minutes: number; daily_minutes?: number; study_days_per_week?: number; learning_format?: string; timeframe_weeks?: number | null; preferred_language: string; active?: boolean };
type Skill = { skill_key: string; proficiency: string };
type RoadmapVersion = { version_number: number; change_reason: string; created_at: string };
type SavedResource = { id: string; resource_url: string; title: string; kind: string; free: boolean | null; created_at: string };
type GapAnalysis = { provider: string; summary_en: string; summary_te: string; disclaimer: string; advice: { skill_key: string; priority: number; estimated_hours: number; explanation_en: string; explanation_te: string; next_step_en: string; next_step_te: string }[] };

export function CareerRoadmap() {
  const token = getToken();
  const headers = useMemo(() => ({ Authorization: `Bearer ${token ?? ""}` }), [token]);
  const [directions, setDirections] = useState<Direction[]>([]);
  const [skills, setSkills] = useState<Record<string, { name: string; name_te?: string; prerequisites: string[] }>>({});
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [goal, setGoal] = useState<Goal | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [careerKey, setCareerKey] = useState("");
  const [customGoal, setCustomGoal] = useState("");
  const [education, setEducation] = useState("beginner");
  const [language, setLanguage] = useState("mixed");
  const [weeklyHours, setWeeklyHours] = useState(5);
  const [interests, setInterests] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [fieldOfStudy, setFieldOfStudy] = useState("");
  const [experienceSummary, setExperienceSummary] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(120);
  const [studyDays, setStudyDays] = useState(5);
  const [learningFormat, setLearningFormat] = useState("mixed");
  const [timeframeWeeks, setTimeframeWeeks] = useState(24);
  const [constraints, setConstraints] = useState("");
  const [versions, setVersions] = useState<RoadmapVersion[]>([]);
  const [savedResources, setSavedResources] = useState<SavedResource[]>([]);
  const [analysis, setAnalysis] = useState<GapAnalysis | null>(null);
  const [mentorQuestion, setMentorQuestion] = useState("");
  const [mentorAnswer, setMentorAnswer] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeConsent, setResumeConsent] = useState(false);
  const [resumeProfile, setResumeProfile] = useState<ResumeProfile | null>(null);
  const [resumeSelected, setResumeSelected] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [viewLanguage, setViewLanguage] = useState<"english" | "telugu" | "mixed">("english");
  const [lesson, setLesson] = useState<{ title: string; content: string; course_id: string; lesson_id: string; completed: boolean } | null>(null);
  const [quiz, setQuiz] = useState<{ attempt_id: string; prompt: string; options: string[]; topic: string } | null>(null);
  const [quizResult, setQuizResult] = useState<{ feedback: string; is_correct: boolean | null } | null>(null);
  const [studyMinutes, setStudyMinutes] = useState(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    let active = true;
    Promise.all([
      request<{ directions: Direction[] }>("/career/directions", { headers }),
      request<{ skills: Record<string, { name: string; name_te?: string; prerequisites: string[] }>; profile: Skill[] }>("/career/skills", { headers }),
      request<Goal[]>("/career/goals", { headers }),
    ]).then(async ([d, s, goals]) => {
      if (!active) return;
      setDirections(d.directions); setSkills(s.skills);
      setSelected(Object.fromEntries(s.profile.map(item => [item.skill_key, item.proficiency])));
      const existing = goals.find(item => item.active) ?? goals[0];
      if (existing) {
        setGoal(existing); setCareerKey(existing.career_key); setEducation(existing.education_level);
        setLanguage(existing.preferred_language); setViewLanguage(existing.preferred_language as "english" | "telugu" | "mixed"); setWeeklyHours(Math.max(1, Math.round(existing.weekly_minutes / 60)));
        setInterests(existing.interests.join(", ")); setCustomGoal(existing.custom_goal ?? ""); setTargetDate(existing.target_date ?? "");
        setFieldOfStudy(existing.field_of_study ?? ""); setDailyMinutes(existing.daily_minutes ?? 120);
        setExperienceSummary(existing.experience_summary ?? "");
        setResumeProfile(existing.resume_profile ?? null);
        setResumeSelected(Object.fromEntries((existing.resume_profile?.skills ?? []).map(item => [item.skill_key, item.proficiency])));
        setStudyDays(existing.study_days_per_week ?? 5); setLearningFormat(existing.learning_format ?? "mixed");
        setTimeframeWeeks(existing.timeframe_weeks ?? 24); setConstraints((existing.constraints ?? []).join(", "));
        const plan = await request<Roadmap>(`/career/goals/${existing.id}/roadmap`, { headers });
        const history = await request<RoadmapVersion[]>(`/career/goals/${existing.id}/versions`, { headers });
        const savedAnalysis = await request<GapAnalysis | null>(`/career/goals/${existing.id}/analysis`, { headers });
        const saved = await request<SavedResource[]>(`/career/goals/${existing.id}/saved-resources`, { headers });
        if (active) { setRoadmap(plan); setVersions(history); setAnalysis(savedAnalysis); setSavedResources(saved); setStudyMinutes(plan.study_adjustment.current_week_studied_minutes); setReady(true); }
      }
    }).catch(cause => { if (active) setError(cause instanceof ApiError ? cause.message : "Could not load career planner."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [headers, token]);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const majorChange = Boolean(goal && (goal.career_key !== careerKey || (goal.custom_goal ?? null) !== (careerKey === "custom" ? customGoal : null)));
      if (majorChange && !window.confirm("This changes your career direction. Your current roadmap and progress history will be kept. Continue?")) { setBusy(false); return; }
      const payload = { career_key: careerKey, custom_goal: careerKey === "custom" ? customGoal : null, education_level: education, field_of_study: fieldOfStudy || null, experience_summary: experienceSummary || null, interests: interests.split(",").map(x => x.trim()).filter(Boolean), constraints: constraints.split(",").map(x => x.trim()).filter(Boolean), weekly_minutes: weeklyHours * 60, daily_minutes: dailyMinutes, study_days_per_week: studyDays, learning_format: learningFormat, timeframe_weeks: timeframeWeeks || null, preferred_language: language, target_date: targetDate || null, confirm_major_change: majorChange };
      const saved = goal
        ? await request<Goal>(`/career/goals/${goal.id}`, { method: "PUT", headers, body: JSON.stringify(payload) })
        : await request<Goal>("/career/goals", { method: "POST", headers, body: JSON.stringify(payload) });
      await request("/career/skills", { method: "PUT", headers, body: JSON.stringify(Object.entries(selected).map(([skill_key, proficiency]) => ({ skill_key, proficiency }))) });
      const plan = await request<Roadmap>(`/career/goals/${saved.id}/roadmap`, { method: "POST", headers });
      const history = await request<RoadmapVersion[]>(`/career/goals/${saved.id}/versions`, { headers });
      const savedCatalog = await request<SavedResource[]>(`/career/goals/${saved.id}/saved-resources`, { headers });
      setGoal(saved); setRoadmap(plan); setVersions(history); setSavedResources(savedCatalog); setAnalysis(null); setStudyMinutes(plan.study_adjustment.current_week_studied_minutes); setReady(true);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not create your roadmap."); }
    finally { setBusy(false); }
  }

  async function complete(milestone: string) {
    if (!goal) return;
    setBusy(true); setError("");
    try { setRoadmap(await request<Roadmap>(`/career/goals/${goal.id}/milestones/${milestone}/complete`, { method: "POST", headers })); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not update milestone."); }
    finally { setBusy(false); }
  }
  async function replan() {
    if (!goal) return;
    setBusy(true); setError("");
    try {
      const next = await request<Roadmap>(`/career/goals/${goal.id}/replan`, { method: "POST", headers });
      setRoadmap(next); setVersions(await request<RoadmapVersion[]>(`/career/goals/${goal.id}/versions`, { headers })); setAnalysis(null);
    }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not refresh your roadmap."); }
    finally { setBusy(false); }
  }
  async function runGapAnalysis() {
    if (!goal) return;
    setBusy(true); setError("");
    try { setAnalysis(await request<GapAnalysis>(`/career/goals/${goal.id}/analysis`, { method: "POST", headers })); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Gemini skill-gap analysis is unavailable."); }
    finally { setBusy(false); }
  }
  async function askMentor(event: FormEvent) {
    event.preventDefault();
    if (!goal || !mentorQuestion.trim()) return;
    setBusy(true); setError(""); setMentorAnswer("");
    try {
      const result = await request<{ answer: string }>(`/career/goals/${goal.id}/mentor`, {
        method: "POST", headers, body: JSON.stringify({ question: mentorQuestion.trim(), language: viewLanguage }),
      });
      setMentorAnswer(result.answer); setMentorQuestion("");
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Career mentor is unavailable."); }
    finally { setBusy(false); }
  }
  async function uploadResume(event: FormEvent) {
    event.preventDefault();
    if (!goal || !resumeFile || !resumeConsent) return;
    setBusy(true); setError("");
    try {
      const body = new FormData(); body.append("file", resumeFile, resumeFile.name);
      const document = await request<{ id: string }>("/documents", { method: "POST", headers, body });
      const parsed = await request<ResumeProfile>(`/career/goals/${goal.id}/resume/extract`, {
        method: "POST", headers, body: JSON.stringify({ document_id: document.id }),
      });
      setResumeProfile(parsed); setResumeSelected(Object.fromEntries(parsed.skills.map(item => [item.skill_key, item.proficiency])));
      setResumeFile(null); setResumeConsent(false);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not extract this resume."); }
    finally { setBusy(false); }
  }
  async function reviewResume() {
    if (!goal || !resumeProfile) return;
    setBusy(true); setError("");
    try {
      const skillsToReview = Object.entries(resumeSelected).filter(([, value]) => value).map(([skill_key, proficiency]) => ({ skill_key, proficiency }));
      const result = await request<{ skills: Skill[]; experience_summary?: string }>(`/career/goals/${goal.id}/resume/profile`, {
        method: "PUT", headers, body: JSON.stringify({ skills: skillsToReview, experience_summary: experienceSummary || resumeProfile.experience_summary, field_of_study: fieldOfStudy || resumeProfile.field_of_study }),
      });
      setSelected(Object.fromEntries(result.skills.map(item => [item.skill_key, item.proficiency])));
      const plan = await request<Roadmap>(`/career/goals/${goal.id}/replan`, { method: "POST", headers });
      setRoadmap(plan); setVersions(await request<RoadmapVersion[]>(`/career/goals/${goal.id}/versions`, { headers }));
      setResumeProfile({ ...resumeProfile, status: "reviewed" });
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not save reviewed resume skills."); }
    finally { setBusy(false); }
  }
  async function toggleSavedResource(resource: { title: string; url: string }) {
    if (!goal) return;
    setBusy(true); setError("");
    try {
      const saved = savedResources.find(item => item.resource_url === resource.url);
      if (saved) {
        await request<void>(`/career/goals/${goal.id}/saved-resources/${saved.id}`, { method: "DELETE", headers });
        setSavedResources(items => items.filter(item => item.id !== saved.id));
      } else {
        const item = await request<SavedResource>(`/career/goals/${goal.id}/saved-resources`, { method: "POST", headers, body: JSON.stringify({ resource_url: resource.url }) });
        setSavedResources(items => items.some(existing => existing.id === item.id) ? items : [item, ...items]);
      }
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not update saved resources."); }
    finally { setBusy(false); }
  }
  async function showVersion(version: number) {
    if (!goal) return;
    setBusy(true); setError("");
    try { setRoadmap(await request<Roadmap>(`/career/goals/${goal.id}/versions/${version}`, { headers })); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not load that roadmap version."); }
    finally { setBusy(false); }
  }
  async function openLesson(courseId: string, lessonId: string, completed: boolean) {
    setBusy(true); setError("");
    try { const result = await request<{ title: string; content: string }>(`/courses/${courseId}/lessons/${lessonId}`, { headers }); setLesson({ ...result, course_id: courseId, lesson_id: lessonId, completed }); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not open this catalog lesson."); }
    finally { setBusy(false); }
  }
  async function markLessonComplete() {
    if (!goal || !lesson) return;
    setBusy(true); setError("");
    try { const next = await request<Roadmap>(`/career/goals/${goal.id}/lessons/${lesson.lesson_id}/complete`, { method: "POST", headers }); setRoadmap(next); setLesson({ ...lesson, completed: true }); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not record lesson completion."); }
    finally { setBusy(false); }
  }
  async function saveStudyMinutes(event: FormEvent) {
    event.preventDefault();
    if (!goal || !roadmap) return;
    setBusy(true); setError("");
    try {
      await request(`/career/goals/${goal.id}/weekly-progress`, { method: "PUT", headers, body: JSON.stringify({ week_start: roadmap.study_adjustment.current_week_start, studied_minutes: studyMinutes }) });
      const next = await request<Roadmap>(`/career/goals/${goal.id}/replan`, { method: "POST", headers });
      setRoadmap(next); setStudyMinutes(next.study_adjustment.current_week_studied_minutes);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not save this week's study time."); }
    finally { setBusy(false); }
  }
  async function startQuiz(topic: string) {
    if (!goal) return;
    setBusy(true); setError(""); setQuizResult(null);
    try {
      const session = await request<{ id: string }>("/sessions", { method: "POST", headers, body: JSON.stringify({ topic, language: goal.preferred_language }) });
      const issued = await request<{ attempt_id: string; prompt: string; options: string[]; topic: string }>(`/assessments/sessions/${session.id}/issue`, { method: "POST", headers });
      setQuiz(issued);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "No objective quiz is available for this skill yet."); }
    finally { setBusy(false); }
  }
  async function answerQuiz(answer: string) {
    if (!quiz) return;
    setBusy(true); setError("");
    try {
      const result = await request<{ feedback: string; is_correct: boolean | null }>(`/assessments/${quiz.attempt_id}/answer`, { method: "POST", headers, body: JSON.stringify({ answer }) });
      setQuizResult(result);
      const fresh = await request<Roadmap>(`/career/goals/${goal!.id}/replan`, { method: "POST", headers });
      setRoadmap(fresh);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Could not submit this answer."); }
    finally { setBusy(false); }
  }

  if (!token) return <Navigate to="/login" replace />;
  if (loading) return <main className="career-page"><p role="status">Loading your career planner?</p></main>;
  const text = viewLanguage === "telugu";
  const mixed = viewLanguage === "mixed";
  const bilingual = (english: string, telugu: string) => text ? telugu : mixed ? `${english} ? ${telugu}` : english;
  const progress = roadmap ? percentComplete(roadmap) : 0;
  return <main className="career-page">
    <header className="career-top"><Link to="/dashboard" className="career-brand">âœ¦ BHASHA<span>LEARN</span> AI</Link><div className="career-actions"><label htmlFor="career-language">{bilingual("Roadmap language", "à°®à°¾à°°à±à°—à°¦à°°à±à°¶à°• à°­à°¾à°·")}</label><select id="career-language" value={viewLanguage} onChange={event => { const next = event.target.value as "english" | "telugu" | "mixed"; setViewLanguage(next); setLanguage(next); }}><option value="english">English</option><option value="telugu">à°¤à±†à°²à±à°—à±</option><option value="mixed">Telugu + English</option></select><Link to="/dashboard">Dashboard</Link></div></header>
    <section className="career-wrap">
      <span className="career-kicker">FUTURE SEEKER Â· YOUR NEXT CHAPTER</span><h1>{text ? "à°®à±€ à°…à°­à±à°¯à°¾à°¸ à°®à°¾à°°à±à°—à°¾à°¨à±à°¨à°¿ à°¨à°¿à°°à±à°®à°¿à°‚à°šà°‚à°¡à°¿" : "Shape your future with a learning roadmap"}</h1>
      <p className="career-intro">{bilingual("Choose a direction, tell us what you already know, and get a practical learning plan that fits your week.", "à°®à±€ à°²à°•à±à°·à±à°¯à°¾à°¨à±à°¨à°¿ à°Žà°‚à°šà±à°•à±à°¨à°¿, à°®à±€à°•à± à°¤à±†à°²à°¿à°¸à°¿à°¨ à°¨à±ˆà°ªà±à°£à±à°¯à°¾à°²à°¨à± à°¤à±†à°²à°¿à°¯à°œà±‡à°¯à°‚à°¡à°¿. à°®à±€ à°¸à°®à°¯à°¾à°¨à°¿à°•à°¿ à°¸à°°à°¿à°ªà±‹à°¯à±‡ à°…à°­à±à°¯à°¾à°¸ à°ªà±à°°à°£à°¾à°³à°¿à°•à°¨à± à°ªà±Šà°‚à°¦à°‚à°¡à°¿.")}</p>
      {error && <div className="career-error" role="alert">{error}</div>}
      {!ready && <form className="career-form" onSubmit={submit}>
        <fieldset><legend>{bilingual("1. Choose a career direction", "1. à°•à±†à°°à±€à°°à± à°²à°•à±à°·à±à°¯à°¾à°¨à±à°¨à°¿ à°Žà°‚à°šà±à°•à±‹à°‚à°¡à°¿")}</legend><div className="career-directions">{directions.map(item => <label className={careerKey === item.career_key ? "career-direction chosen" : "career-direction"} key={item.career_key}><input type="radio" name="career" value={item.career_key} required checked={careerKey === item.career_key} onChange={() => setCareerKey(item.career_key)}/><strong>{bilingual(item.title, item.title_te ?? item.title)}</strong><small>{item.required_skills.length} connected skills Â· general guidance</small></label>)}</div></fieldset>
        {careerKey === "custom" && <label className="career-custom-goal">Describe the learning goal<input required maxLength={160} value={customGoal} onChange={event => setCustomGoal(event.target.value)} placeholder="e.g. learn robotics foundations"/></label>}
        <div className="career-input-grid"><label>{bilingual("Current education level", "à°ªà±à°°à°¸à±à°¤à±à°¤ à°µà°¿à°¦à±à°¯à°¾ à°¸à±à°¥à°¾à°¯à°¿")}<select value={education} onChange={event => setEducation(event.target.value)}><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></label><label>{bilingual("Field of study", "à°µà°¿à°¦à±à°¯à°¾ à°µà°¿à°­à°¾à°—à°‚")}<input maxLength={120} value={fieldOfStudy} onChange={event => setFieldOfStudy(event.target.value)} placeholder="e.g. computer science"/></label><label>{bilingual("Weekly study hours", "à°µà°¾à°°à°¾à°¨à°¿à°•à°¿ à°…à°­à±à°¯à°¾à°¸ à°—à°‚à°Ÿà°²à±")}<input type="number" min={1} max={40} value={weeklyHours} onChange={event => setWeeklyHours(Number(event.target.value))}/></label><label>{bilingual("Available minutes per study day", "à°°à±‹à°œà±à°•à± à°…à°‚à°¦à±à°¬à°¾à°Ÿà±à°²à±‹ à°‰à°¨à±à°¨ à°¨à°¿à°®à°¿à°·à°¾à°²à±")}<input type="number" min={15} max={480} value={dailyMinutes} onChange={event => setDailyMinutes(Number(event.target.value))}/></label><label>{bilingual("Study days per week", "à°µà°¾à°°à°¾à°¨à°¿à°•à°¿ à°…à°­à±à°¯à°¾à°¸ à°°à±‹à°œà±à°²à±")}<input type="number" min={1} max={7} value={studyDays} onChange={event => setStudyDays(Number(event.target.value))}/></label><label>{bilingual("Preferred learning format", "à°‡à°·à±à°Ÿà°®à±ˆà°¨ à°…à°­à±à°¯à°¾à°¸ à°µà°¿à°§à°¾à°¨à°‚")}<select value={learningFormat} onChange={event => setLearningFormat(event.target.value)}><option value="mixed">Mixed activities</option><option value="video">Videos</option><option value="reading">Reading</option><option value="practice">Hands-on practice</option></select></label><label>{bilingual("Preferred learning language", "à°‡à°·à±à°Ÿà°®à±ˆà°¨ à°…à°­à±à°¯à°¾à°¸ à°­à°¾à°·")}<select value={language} onChange={event => setLanguage(event.target.value)}><option value="english">English</option><option value="telugu">à°¤à±†à°²à±à°—à±</option><option value="mixed">Telugu + English</option></select></label><label>{bilingual("Interests", "à°†à°¸à°•à±à°¤à±à°²à±")}<input maxLength={500} value={interests} onChange={event => setInterests(event.target.value)} placeholder="e.g. building apps, solving problems"/></label><label>{bilingual("Learning constraints", "à°…à°­à±à°¯à°¾à°¸ à°ªà°°à°¿à°®à°¿à°¤à±à°²à±")}<input maxLength={500} value={constraints} onChange={event => setConstraints(event.target.value)} placeholder="e.g. phone only, shared computer"/></label><label>{bilingual("Target timeframe in weeks", "à°²à°•à±à°·à±à°¯ à°—à°¡à±à°µà± (à°µà°¾à°°à°¾à°²à±)")}<input type="number" min={1} max={260} value={timeframeWeeks} onChange={event => setTimeframeWeeks(Number(event.target.value))}/></label><label>{bilingual("Optional target completion date", "à°à°šà±à°›à°¿à°• à°ªà±‚à°°à±à°¤à°¿ à°¤à±‡à°¦à±€")}<input type="date" value={targetDate} onChange={event => setTargetDate(event.target.value)}/></label></div>
        <fieldset><legend>{bilingual("2. Assess your current skills", "2. à°®à±€ à°ªà±à°°à°¸à±à°¤à±à°¤ à°¨à±ˆà°ªà±à°£à±à°¯à°¾à°²à°¨à± à°…à°‚à°šà°¨à°¾ à°µà±‡à°¯à°‚à°¡à°¿")} <span className="career-muted">{bilingual("Self-assessment does not count as verified mastery.", "à°¸à±à°µà±€à°¯ à°…à°‚à°šà°¨à°¾ à°¨à°¿à°°à±à°§à°¾à°°à°¿à°¤ à°¨à±ˆà°ªà±à°£à±à°¯à°‚à°—à°¾ à°ªà°°à°¿à°—à°£à°¿à°‚à°šà°¬à°¡à°¦à±.")}</span></legend><div className="skill-grid">{Object.entries(skills).map(([key, skill]) => <label className="skill-row" key={key}><span>{bilingual(skill.name, skill.name_te ?? skill.name)}<small>{skill.prerequisites.length ? `Needs: ${skill.prerequisites.map(p => skills[p]?.name ?? p).join(", ")}` : "Foundation skill"}</small></span><select aria-label={`${skill.name} self-assessed proficiency`} value={selected[key] ?? ""} onChange={event => setSelected(prev => ({ ...prev, [key]: event.target.value }))}><option value="">Not yet assessed</option><option value="unknown">I am unsure</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></label>)}</div></fieldset>
        <label>{bilingual("Experience so far", "à°‡à°ªà±à°ªà°Ÿà°¿à°µà°°à°•à± à°…à°¨à±à°­à°µà°‚")}<textarea aria-label="Experience summary" maxLength={1200} value={experienceSummary} onChange={event => setExperienceSummary(event.target.value)} placeholder="Projects, internships, work, or relevant experience" /></label>
        <button className="career-primary" disabled={busy || !careerKey}>{busy ? "Building your roadmap?" : "Create my roadmap"}</button>
      </form>}
      {ready && roadmap && <>
        <section className="roadmap-summary"><div><span className="career-kicker">GENERAL CAREER GUIDANCE Â· NOT A LIVE JOB FORECAST Â· VERSION {roadmap.version_number}</span><h2>{bilingual(roadmap.career_title, roadmap.career_title_te ?? roadmap.career_title)}</h2><p>{bilingual(roadmap.summary, roadmap.summary_te)}</p><p>{bilingual(`Estimated learning effort: ${roadmap.total_estimated_hours} hours Â· about ${roadmap.estimated_weeks} weeks at your planned pace.`, `à°…à°‚à°šà°¨à°¾ à°…à°­à±à°¯à°¾à°¸ à°¸à°®à°¯à°‚: ${roadmap.total_estimated_hours} à°—à°‚à°Ÿà°²à± Â· à°®à±€ à°ªà±à°°à°£à°¾à°³à°¿à°• à°ªà±à°°à°•à°¾à°°à°‚ à°¸à±à°®à°¾à°°à± ${roadmap.estimated_weeks} à°µà°¾à°°à°¾à°²à±.`)}</p><p><b>Learning readiness: {roadmap.readiness.score}%</b> Â· {roadmap.readiness.basis}</p></div><div className="roadmap-progress"><strong>{progress}%</strong><span>{roadmap.progress.completed_milestones} of {roadmap.progress.total_milestones} milestones</span><div className="progress-track"><i style={{ width: `${progress}%` }}/></div></div></section>
        <div className="roadmap-heading"><div><span className="career-kicker">YOUR LEARNING PATH</span><h2>{bilingual("From foundations to portfolio", "à°ªà±à°¨à°¾à°¦à±à°² à°¨à±à°‚à°šà°¿ à°ªà±‹à°°à±à°Ÿà±â€Œà°«à±‹à°²à°¿à°¯à±‹ à°µà°°à°•à±")}</h2></div><div className="career-actions"><button className="career-secondary" disabled={busy} onClick={runGapAnalysis}>Analyze skill gaps with Gemini</button><button className="career-secondary" onClick={() => { setReady(false); setRoadmap(null); }}>{bilingual("Edit goal & skills", "à°²à°•à±à°·à±à°¯à°‚ à°®à°°à°¿à°¯à± à°¨à±ˆà°ªà±à°£à±à°¯à°¾à°²à°¨à± à°¸à°µà°°à°¿à°‚à°šà°‚à°¡à°¿")}</button><button className="career-secondary" disabled={busy} onClick={replan}>{bilingual("Replan", "à°ªà±à°°à°£à°¾à°³à°¿à°•à°¨à± à°¨à°µà±€à°•à°°à°¿à°‚à°šà°‚à°¡à°¿")}</button><label>Roadmap history <select aria-label="Roadmap history" value={roadmap.version_number} onChange={event => void showVersion(Number(event.target.value))}>{versions.map(item => <option key={item.version_number} value={item.version_number}>Version {item.version_number} Â· {item.change_reason.replaceAll("_", " ")}</option>)}</select></label></div></div>
        {analysis && <section className="roadmap-summary" aria-label="Gemini skill gap analysis"><div><span className="career-kicker">GEMINI GUIDANCE Â· {analysis.provider}</span><p>{viewLanguage === "telugu" ? analysis.summary_te : viewLanguage === "mixed" ? `${analysis.summary_en} Â· ${analysis.summary_te}` : analysis.summary_en}</p><ul className="gap-list">{analysis.advice.sort((a,b) => a.priority - b.priority).map(item => <li key={item.skill_key}><b>{skills[item.skill_key]?.name ?? item.skill_key} Â· priority {item.priority} Â· ~{item.estimated_hours} hours</b><span>{viewLanguage === "telugu" ? item.explanation_te : item.explanation_en}</span><small>{viewLanguage === "telugu" ? item.next_step_te : item.next_step_en}</small></li>)}</ul><p className="career-muted">{analysis.disclaimer}</p></div></section>}
        <section className="roadmap-summary" aria-label="Resume profile"><div><span className="career-kicker">PRIVATE RESUME PROFILE</span><h3>Review skills from your resume</h3><p>Upload PDF or DOCX. Resume text is sent to Gemini only after you consent. Confirm suggestions before they update your persistent profile.</p><form className="study-log-form" onSubmit={uploadResume}><label>Resume file<input aria-label="Resume file" type="file" accept="application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx" onChange={event => setResumeFile(event.target.files?.[0] ?? null)} /></label><label><input type="checkbox" checked={resumeConsent} onChange={event => setResumeConsent(event.target.checked)} /> I consent to sending extracted resume text to Gemini for skill suggestions.</label><button className="career-secondary" disabled={busy || !resumeFile || !resumeConsent}>Upload and analyze resume</button></form>{resumeProfile && <div><h4>{resumeProfile.filename} · {resumeProfile.status.replaceAll("_", " ")}</h4>{resumeProfile.status === "awaiting_review" ? <><ul className="gap-list">{resumeProfile.skills.map(item => <li key={item.skill_key}><label><input type="checkbox" checked={Boolean(resumeSelected[item.skill_key])} onChange={event => setResumeSelected(prev => ({ ...prev, [item.skill_key]: event.target.checked ? item.proficiency : "" }))} />{skills[item.skill_key]?.name ?? item.skill_key}<small>{item.evidence}</small></label><select aria-label={`${item.skill_key} reviewed proficiency`} disabled={!resumeSelected[item.skill_key]} value={resumeSelected[item.skill_key] ?? ""} onChange={event => setResumeSelected(prev => ({ ...prev, [item.skill_key]: event.target.value }))}><option value="">Not confirmed</option><option value="unknown">Unsure</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></li>)}</ul><button className="career-primary" disabled={busy} onClick={() => void reviewResume()}>Save reviewed profile and update roadmap</button></> : <p role="status">Resume skills reviewed. You can upload a new resume at any time.</p>}</div>}</div></section>                <section className="roadmap-summary" aria-label="AI career mentor"><div><span className="career-kicker">FUTURE SEEKER MENTOR Â· GEMINI</span><h3>{bilingual("Ask about your current roadmap", "à°®à±€ à°ªà±à°°à°¸à±à°¤à±à°¤ à°…à°­à±à°¯à°¾à°¸ à°®à°¾à°°à±à°—à°‚ à°—à±à°°à°¿à°‚à°šà°¿ à°…à°¡à°—à°‚à°¡à°¿")}</h3><p>{bilingual("Answers use your saved skills, roadmap version, progress, and weekly study plan.", "à°®à±€ à°¸à±‡à°µà± à°šà±‡à°¸à°¿à°¨ à°¨à±ˆà°ªà±à°£à±à°¯à°¾à°²à±, à°°à±‹à°¡à±â€Œà°®à±à°¯à°¾à°ªà±, à°ªà±à°°à±‹à°—à°¤à°¿, à°µà°¾à°°à°ªà± à°ªà±à°°à°£à°¾à°³à°¿à°• à°†à°§à°¾à°°à°‚à°—à°¾ à°¸à°®à°¾à°§à°¾à°¨à°¾à°²à± à°µà°¸à±à°¤à°¾à°¯à°¿.")}</p><form className="study-log-form" onSubmit={askMentor}><label>{bilingual("Your question", "à°®à±€ à°ªà±à°°à°¶à±à°¨")}<input aria-label="Career mentor question" maxLength={1200} value={mentorQuestion} onChange={event => setMentorQuestion(event.target.value)} placeholder="What should I focus on next?" /></label><button className="career-secondary" disabled={busy || !mentorQuestion.trim()}>{bilingual("Ask mentor", "à°®à±†à°‚à°Ÿà°°à±â€Œà°¨à± à°…à°¡à°—à°‚à°¡à°¿")}</button></form>{mentorAnswer && <p role="status">{mentorAnswer}</p>}</div></section>
        <CareerRoadmapGraph phases={roadmap.phases} onSelect={milestone => { const index = roadmap.phases.findIndex(phase => phase.milestone_id === milestone); document.querySelectorAll(".phase-card")[index]?.scrollIntoView({ behavior: "smooth", block: "center" }); }} />
        <Link className="career-secondary" to={`/voice?careerGoalId=${encodeURIComponent(goal?.id ?? "")}`}>Open bilingual Gnani voice mentor</Link>
        <div className="career-layout"><section className="phase-list" aria-label="Career roadmap timeline">{roadmap.phases.map((phase, index) => <article className={`phase-card ${phase.completed ? "phase-done" : ""}`} key={phase.milestone_id}><div className="phase-number">{phase.completed ? "âœ“" : String(index + 1).padStart(2, "0")}</div><div className="phase-main"><div className="phase-title"><div><span className="career-kicker">PHASE {index + 1} Â· {phase.estimated_hours} HOURS</span><h3>{bilingual(phase.title, phase.title_te)}</h3></div><span className="skill-status">{gapLabel(roadmap.skill_gaps.find(item => item.skill_key === phase.skill_key)?.status ?? "recommended_next", viewLanguage)}</span></div><p>Prerequisites: {phase.prerequisite_skills.map(key => bilingual(skills[key]?.name ?? key, skills[key]?.name_te ?? skills[key]?.name ?? key)).join(", ") || "None"}</p>{phase.course_id && <p className="catalog-link">Course: {phase.course_title}{phase.lesson_id ? ` Â· Lesson: ${phase.lesson_title}` : ""}</p>}{phase.course_id && phase.lesson_id && <button className="study-lesson-button" disabled={busy} onClick={() => openLesson(phase.course_id!, phase.lesson_id!, phase.lesson_completed)}>{bilingual("Study recommended lesson", "à°¸à±‚à°šà°¿à°‚à°šà°¿à°¨ à°ªà°¾à° à°¾à°¨à±à°¨à°¿ à°…à°­à±à°¯à°¸à°¿à°‚à°šà°‚à°¡à°¿")}</button>}{phase.lesson_completed && <span className="lesson-done-label">Lesson completed</span>}<p className="milestone-description">{bilingual(phase.milestone_description, phase.milestone_description_te)}</p><div className="phase-activities"><p><b>{bilingual("Practice", "à°¸à°¾à°§à°¨")}</b> {bilingual(phase.practice, phase.practice_te)}</p><p><b>{bilingual("Assessment", "à°®à°¦à°¿à°‚à°ªà±")}</b> {phase.assessment}</p>{phase.assessment_topic && <button className="study-lesson-button" disabled={busy} onClick={() => startQuiz(phase.assessment_topic!)}>{bilingual("Start objective quiz", "à°¨à±ˆà°ªà±à°£à±à°¯ à°ªà°°à±€à°•à±à°· à°ªà±à°°à°¾à°°à°‚à°­à°¿à°‚à°šà°‚à°¡à°¿")}</button>}<p><b>{bilingual("Portfolio", "à°ªà±‹à°°à±à°Ÿà±â€Œà°«à±‹à°²à°¿à°¯à±‹")}</b> {phase.project}</p>{phase.resources?.length > 0 && <ul className="career-resources" aria-label={`Resources for ${phase.title}`}>{phase.resources.map(resource => { const saved = savedResources.some(item => item.resource_url === resource.url); return <li key={resource.url}><a href={resource.url} target="_blank" rel="noopener noreferrer">{resource.title}</a><small>{resource.kind} Â· {resource.free === true ? "Free" : resource.free === false ? "Paid" : "Access varies"}</small><button className="career-secondary" aria-pressed={saved} disabled={busy} onClick={() => toggleSavedResource(resource)}>{bilingual(saved ? "Remove saved resource" : "Save resource", saved ? "à°¸à±‡à°µà± à°šà±‡à°¸à°¿à°¨ à°µà°¨à°°à±à°¨à± à°¤à±Šà°²à°—à°¿à°‚à°šà°‚à°¡à°¿" : "à°µà°¨à°°à±à°¨à± à°¸à±‡à°µà± à°šà±‡à°¯à°‚à°¡à°¿")}</button></li>; })}</ul>}</div><button className="milestone-button" disabled={phase.completed || busy} onClick={() => complete(phase.milestone_id)}>{phase.completed ? bilingual("Milestone completed", "à°®à±ˆà°²à±à°°à°¾à°¯à°¿ à°ªà±‚à°°à±à°¤à°¯à°¿à°‚à°¦à°¿") : bilingual("Complete milestone", "à°®à±ˆà°²à±à°°à°¾à°¯à°¿à°¨à°¿ à°ªà±‚à°°à±à°¤à°¿ à°šà±‡à°¯à°‚à°¡à°¿")}</button></div></article>)}</section>
          <aside className="planner-card"><span className="career-kicker">{bilingual("THIS WEEK", "à°ˆ à°µà°¾à°°à°‚")}</span><h3>{bilingual("Study planner", "à°…à°­à±à°¯à°¾à°¸ à°ªà±à°°à°£à°¾à°³à°¿à°•")}</h3><p>{Math.round(roadmap.study_adjustment.recommended_weekly_minutes / 60)} hours Â· flexible sessions</p>{roadmap.study_adjustment.state === "missed_last_week" && <p className="study-adjustment" role="status">Last week: {roadmap.study_adjustment.previous_studied_minutes} of {roadmap.study_adjustment.previous_target_minutes} minutes. This week uses shorter focused blocks.</p>}<ul>{roadmap.weekly_plan.map(day => <li key={day.day}><b>{day.day}</b><span>{day.minutes} min</span></li>)}</ul><form className="study-log-form" onSubmit={saveStudyMinutes}><label>Minutes studied this week<input aria-label="Minutes studied this week" type="number" min={0} max={2400} value={studyMinutes} onChange={event => setStudyMinutes(Number(event.target.value))}/></label><button className="career-secondary" disabled={busy}>Save study time</button></form><p className="career-muted">Current log: {roadmap.study_adjustment.current_week_studied_minutes} min Â· target {goal?.weekly_minutes} min</p>{savedResources.length > 0 && <section aria-label="Saved learning resources"><h3>{bilingual("Saved resources", "à°¸à±‡à°µà± à°šà±‡à°¸à°¿à°¨ à°…à°­à±à°¯à°¾à°¸ à°µà°¨à°°à±à°²à±")}</h3><ul className="career-resources">{savedResources.map(item => <li key={item.id}><a href={item.resource_url} target="_blank" rel="noopener noreferrer">{item.title}</a><small>{item.kind} Â· {item.free === true ? "Free" : item.free === false ? "Paid" : "Access varies"}</small></li>)}</ul></section>}<h3>Skill gap snapshot</h3><ul className="gap-list">{roadmap.skill_gaps.map(item => <li key={item.skill_key}><span>{bilingual(item.name, skills[item.skill_key]?.name_te ?? item.name)}</span><small>{gapLabel(item.status, viewLanguage)}</small></li>)}</ul><p className="career-muted">Reported proficiency stays unverified until supported by learning evidence.</p></aside>
        </div>
      </>}
    </section>
    {lesson && <div className="lesson-backdrop" role="presentation" onClick={() => setLesson(null)}><section className="lesson-dialog" role="dialog" aria-modal="true" aria-labelledby="lesson-title" onClick={event => event.stopPropagation()}><button className="lesson-close" aria-label="Close lesson" onClick={() => setLesson(null)}>?</button><span className="career-kicker">CATALOG LESSON</span><h2 id="lesson-title">{lesson.title}</h2><div className="lesson-content">{lesson.content}</div><button className="milestone-button lesson-complete-action" disabled={busy || lesson.completed} onClick={markLessonComplete}>{lesson.completed ? "Lesson completed" : "Mark lesson complete"}</button></section></div>}
    {quiz && <div className="lesson-backdrop" role="presentation" onClick={() => { setQuiz(null); setQuizResult(null); }}><section className="lesson-dialog" role="dialog" aria-modal="true" aria-labelledby="quiz-title" onClick={event => event.stopPropagation()}><button className="lesson-close" aria-label="Close quiz" onClick={() => { setQuiz(null); setQuizResult(null); }}>?</button><span className="career-kicker">OBJECTIVE PRACTICE ? {quiz.topic}</span><h2 id="quiz-title">{quiz.prompt}</h2>{quizResult ? <><p role="status" className="quiz-feedback">{quizResult.feedback}</p><button className="career-secondary" onClick={() => { setQuiz(null); setQuizResult(null); }}>Close quiz</button></> : <div className="quiz-options">{quiz.options.map(option => <button key={option} disabled={busy} onClick={() => answerQuiz(option)}>{option}</button>)}</div>}</section></div>}
  </main>;
}
