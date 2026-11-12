import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, clearToken, getCurrentStudent, getToken, request, type Student } from "./auth";
import { DashboardShell } from "./dashboard/DashboardShell";
import "./course-catalog.css";

type Lesson = { id: string; title: string; estimated_minutes: number; objective: string; content_en: string; content_te: string; quiz_topic: string | null };
type Course = { id: string; title: string; description: string; provider: string; content_type: "in_app"; language: string; level: string; estimated_minutes: number; prerequisites: string[]; skills: string[]; lessons: Lesson[]; lessons_completed: number; progress_percent: number; enrolled: boolean; completed_lesson_ids: string[]; next_lesson_id: string | null; completed: boolean };
type CourseCard = Omit<Course, "lessons"> & { lessons_count: number };

export function CourseCatalog() {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const [student, setStudent] = useState<Student | null>(null);
  const [courses, setCourses] = useState<CourseCard[]>([]);
  const [course, setCourse] = useState<Course | null>(null);
  const [selectedLessonId, setSelectedLessonId] = useState("");
  const [language, setLanguage] = useState<"en" | "te">("en");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const token = getToken();
  const signOut = useCallback(() => { clearToken(); navigate("/login", { replace: true }); }, [navigate]);
  const headers: HeadersInit = token ? { Authorization: "Bearer " + token } : {};

  useEffect(() => {
    let active = true;
    if (!token) { navigate("/login", { replace: true }); return () => { active = false; }; }
    setLoading(true); setError("");
    void (async () => {
      let stage = "student profile";
      try {
        const current = await getCurrentStudent(token);
        stage = "course catalog";
        const list = await request<CourseCard[]>("/courses/catalog", { headers: { Authorization: "Bearer " + token } });
        stage = "course details";
        const detail = courseId ? await request<Course>(`/courses/catalog/${encodeURIComponent(courseId)}`, { headers: { Authorization: "Bearer " + token } }) : null;
        if (active) { setStudent(current); setCourses(list); setCourse(detail); setSelectedLessonId(detail?.next_lesson_id || detail?.lessons[0]?.id || ""); }
      } catch (cause) {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) { signOut(); return; }
        setError(`${stage}: ${cause instanceof Error ? cause.message : "Could not load courses."}`);
      } finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [courseId, navigate, signOut, token]);

  async function enroll() {
    if (!course || busy) return;
    setBusy(true); setError("");
    try {
      const saved = await request<Course>(`/courses/catalog/${encodeURIComponent(course.id)}/enroll`, { method: "POST", headers });
      setCourse(saved); setCourses(items => items.map(item => item.id === saved.id ? { ...item, enrolled: true, progress_percent: saved.progress_percent } : item));
    } catch (cause) { if (cause instanceof ApiError && cause.status === 401) signOut(); else setError(cause instanceof Error ? cause.message : "Could not save enrollment."); }
    finally { setBusy(false); }
  }

  async function completeLesson(lessonId: string) {
    if (!course || busy) return;
    setBusy(true); setError("");
    try {
      const saved = await request<Course>(`/courses/catalog/${encodeURIComponent(course.id)}/lessons/${encodeURIComponent(lessonId)}/complete`, { method: "POST", headers });
      setCourse(saved); setCourses(items => items.map(item => item.id === saved.id ? { ...item, enrolled: true, progress_percent: saved.progress_percent, lessons_completed: saved.lessons_completed, completed: saved.completed } : item));
      setSelectedLessonId(saved.next_lesson_id || lessonId);
    } catch (cause) { if (cause instanceof ApiError && cause.status === 401) signOut(); else setError(cause instanceof Error ? cause.message : "Could not save lesson completion."); }
    finally { setBusy(false); }
  }

  const selectedLesson = course?.lessons.find(item => item.id === selectedLessonId) ?? null;
  if (!student) return <main className="course-catalog-page course-auth-state" role={error ? "alert" : "status"}>
    <h1>{error ? "Courses are unavailable" : "Loading your courses…"}</h1>
    {error && <><p>{error}</p><Link to="/login">Return to sign in</Link></>}
  </main>;
  return <div className="course-catalog-page">{student && <DashboardShell student={student} onSignOut={signOut}><div className="course-page-head"><div><span className="course-eyebrow">LEARN AT YOUR PACE</span><h1>{course ? course.title : "Courses and learning paths"}</h1><p>{course ? course.description : "Choose a BHASHALEARN starter course and keep your lesson progress in your account."}</p></div>{course && <Link className="course-back" to="/courses">← All courses</Link>}</div>
    {error && <p className="course-error" role="alert">{error}</p>}{loading ? <p className="course-state" role="status">Loading your course data…</p> : course ? <>
      <section className="course-overview"><div><strong>{course.provider} · In-app lessons</strong><p>{course.level} · {course.estimated_minutes} minutes · {course.lessons.length} lessons</p><p>Prerequisites: {course.prerequisites.length ? course.prerequisites.join(", ") : "None"}</p><p>Skills: {course.skills.join(" · ")}</p></div><div className="course-progress"><strong>{course.progress_percent}%</strong><span>{course.lessons_completed} of {course.lessons.length} lessons complete</span><progress max={100} value={course.progress_percent} aria-label="Course completion"/></div></section>
      {!course.enrolled ? <div className="course-enroll"><p>Enroll to save this learning path and track lesson completion.</p><button type="button" disabled={busy} onClick={() => void enroll()}>{busy ? "Saving…" : "Save learning path"}</button></div> : <p className="course-enrolled" role="status">Learning path saved for {student.display_name}.</p>}
      <div className="course-detail-grid"><nav className="course-lesson-list" aria-label="Course lessons"><h2>Modules and lessons</h2>{course.lessons.map((lesson,index) => <button type="button" key={lesson.id} className={lesson.id === selectedLessonId ? "selected" : ""} onClick={() => setSelectedLessonId(lesson.id)}><span>{String(index + 1).padStart(2,"0")}</span><strong>{lesson.title}</strong><small>{lesson.estimated_minutes} min {course.completed_lesson_ids.includes(lesson.id) ? "· Complete" : ""}</small></button>)}</nav>
        {selectedLesson ? <article className="course-lesson"><span className="course-eyebrow">LESSON · {selectedLesson.estimated_minutes} MINUTES</span><h2>{selectedLesson.title}</h2><p className="course-objective"><b>Objective:</b> {selectedLesson.objective}</p><div className="course-language"><button type="button" aria-pressed={language === "en"} onClick={() => setLanguage("en")}>English</button><button type="button" aria-pressed={language === "te"} onClick={() => setLanguage("te")}>తెలుగు</button></div><p className="course-lesson-copy">{language === "te" ? selectedLesson.content_te : selectedLesson.content_en}</p><p className="course-source-note">Built-in BHASHALEARN lesson content. It is not generated by Gemini.</p>{!course.enrolled ? <button type="button" disabled={busy} onClick={() => void enroll()}>Save path to track this lesson</button> : course.completed_lesson_ids.includes(selectedLesson.id) ? <p className="course-complete-note">✓ Lesson completion saved.</p> : <button type="button" disabled={busy} onClick={() => void completeLesson(selectedLesson.id)}>{busy ? "Saving…" : "Mark lesson complete"}</button>}</article> : <p>Select a lesson to begin.</p>}</div>
      {course.next_lesson_id && <p className="course-next">Recommended next: {course.lessons.find(item => item.id === course.next_lesson_id)?.title}</p>}{course.completed && <p className="course-complete-note" role="status">Course completed from recorded lesson activity.</p>}
    </> : <section className="course-cards" aria-label="Course catalog">{courses.map(item => <article className="course-card" key={item.id}><span className="course-eyebrow">{item.provider} · {item.level}</span><h2>{item.title}</h2><p>{item.description}</p><p>{item.estimated_minutes} min · {item.lessons_count} lessons · {item.skills.join(" · ")}</p><p>Prerequisites: {item.prerequisites.length ? item.prerequisites.join(", ") : "None"}</p>{item.enrolled && <div className="course-card-progress"><span>{item.lessons_completed}/{item.lessons_count} lessons · {item.progress_percent}%</span><progress max={100} value={item.progress_percent} aria-label={`${item.title} progress`}/></div>}<Link to={`/courses/${item.id}`}>{item.enrolled ? "Continue course" : "View course"} ↗</Link></article>)}</section>}</DashboardShell>}</div>;
}
