# BHASHALEARN 15-screen visual verification

Reference source: [approved contact sheet](./bhashalearn-15-screens.png) and [individual panel crops](./screens/). Captures below were generated from the React/Vite routes in this worktree with Playwright at 1440×1000 and 390×844. Authenticated routes use isolated fixture responses; they are screenshots of the real frontend, not production student data.

## Capture set

| # | Screen | Route | Desktop | Mobile | Visual note |
|---:|---|---|---|---|---|
| 1 | Login | `/login` | [desktop](./captures/01-login-desktop.png) | [mobile](./captures/01-login-mobile.png) | Split navy/lavender sign-in; social controls clearly say Demo because OAuth is not configured. |
| 2 | Registration | `/register` | [desktop](./captures/02-register-desktop.png) | [mobile](./captures/02-register-mobile.png) | Shared auth illustration and form system; existing SVG art is an approximation. |
| 3 | Forgot password | `/forgot-password` | [desktop](./captures/03-forgot-password-desktop.png) | [mobile](./captures/03-forgot-password-mobile.png) | Reset request form and privacy-preserving response. |
| 4 | Dashboard | `/dashboard` | [desktop](./captures/04-dashboard-desktop.png) | [mobile](./captures/04-dashboard-mobile.png) | Violet navigation and responsive account-backed cards. |
| 5 | AI Classroom | `/voice` | [desktop](./captures/05-ai-classroom-desktop.png) | [mobile](./captures/05-ai-classroom-mobile.png) | Existing voice lesson flow; provider calls were not part of this frontend test. |
| 6 | AI Chatbot | `/chat` | [desktop](./captures/06-ai-chatbot-desktop.png) | [mobile](./captures/06-ai-chatbot-mobile.png) | Existing session-backed chat; no Gemini request was made. |
| 7 | PDF Learning Studio | `/documents` | [desktop](./captures/07-pdf-learning-studio-desktop.png) | [mobile](./captures/07-pdf-learning-studio-mobile.png) | Existing upload/library controls; no file was uploaded. |
| 8 | My Courses | `/courses` | [desktop](./captures/08-my-courses-desktop.png) | [mobile](./captures/08-my-courses-mobile.png) | Existing course catalog and progress actions. |
| 9 | Learning Timeline | `/timeline` | [desktop](./captures/09-learning-timeline-desktop.png) | [mobile](./captures/09-learning-timeline-mobile.png) | Timeline layout reads recorded analytics data. |
| 10 | Progress Analytics | `/progress-analytics` | [desktop](./captures/10-progress-analytics-desktop.png) | [mobile](./captures/10-progress-analytics-mobile.png) | Existing evidence-based analytics and empty states. |
| 11 | Settings | `/settings` | [desktop](./captures/11-settings-desktop.png) | [mobile](./captures/11-settings-mobile.png) | Account preferences and responsive form. |
| 12 | Mobile Dashboard | `/dashboard` at 390 px | [desktop](./captures/12-mobile-dashboard-desktop.png) | [mobile](./captures/12-mobile-dashboard-mobile.png) | Same route captured at both viewports; mobile has bottom navigation. |
| 13 | Visual Lesson Studio | `/visual-lessons` | [desktop](./captures/13-visual-lesson-studio-desktop.png) | [mobile](./captures/13-visual-lesson-studio-mobile.png) | New interactive house-and-garden SVG lesson, bilingual vocabulary, steps, and quiz. It follows the reference composition but uses original geometric artwork rather than the reference’s exact illustration. |
| 14 | Certificate | `/certificate` | [desktop](./captures/14-certificate-desktop.png) | [mobile](./captures/14-certificate-mobile.png) | Certificate is only issued for completed course data; capture shows honest empty state. |
| 15 | Practice call scheduler | `/assistant` | [desktop](./captures/15-call-scheduler-desktop.png) | [mobile](./captures/15-call-scheduler-mobile.png) | Practice reminders, tutor character, upcoming sessions, and call history. Incoming-call controls and deeper Feature 2 settings are expandable to keep the reference page concise. |

## Functional checks

- Full Playwright browser suite against an isolated disposable PostgreSQL database and dedicated FastAPI/Vite services: **95 passed, 0 failed, 0 skipped**. The final run used the real application and API for local auth, registration, documents, and student flows; external AI/provider responses and desktop execution are explicitly mocked in the relevant browser tests.
- The browser suite covers the house lesson navigation/vocabulary/quiz/language switch; scheduler deadline creation and incoming-call demo; dashboard/courses/progress/PDF flows; auth; Features 1–5 browser contracts; approval-gated desktop command previews; and desktop/mobile rendering of all 15 routes. It regenerated all **30** screenshots in `captures/` at 1440×1000 and 390×844.
- The reference-screen capture test also checks mobile document width and overflowing top-level elements; all **15 mobile routes** fit the 390px viewport.
- Frontend unit tests: **154 passed, 0 failed** (`npm test`).
- TypeScript and Vite production build: **passed** (`npm run build`). Vite reports the existing Three.js and main bundle chunks over 500 kB; this is a performance warning, not a build failure.
- `git diff --check`: passed.

## Visual differences and limits

This is not a pixel-exact reproduction. The existing React route structure and feature APIs were preserved; some screens still differ from the contact sheet in artwork, text density, typography, card proportions, and exact spacing. The house SVG is a code-native approximation, not a copy of the reference picture. The scheduler uses the existing account deadline and browser/LiveKit call contracts; unavailable provider states remain visible inside expanded controls. OAuth buttons are labeled demos and do not authenticate. Browser captures use test fixtures and do not prove live Gemini, Gnani, LiveKit, telephony, or Windows desktop operation. The isolated full browser suite, unit suite, and production build all pass, so the frontend is ready for a browser-based hackathon demonstration of the tested local flows; live-provider and native Windows demonstrations remain separate prerequisites.
