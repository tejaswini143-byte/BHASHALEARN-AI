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

- Playwright browser tests: **5 passed, 0 failed**. They cover the house lesson stages/vocabulary/quiz/language switch, the existing reminder creation contract, the accessible local incoming-call dialog and snooze behavior, safe social-login demo state, and desktop/mobile rendering of all 15 routes with no uncaught browser errors.
- Preserved regression suites retested after the new disclosures/selectors: assistant **1 passed**, visual lesson engine **5 passed**, Feature 4 lesson integration **2 passed**.
- Full 95-test browser run in frontend-only mode: **74 passed, 13 failed, 8 skipped**. This was not a complete backend acceptance run: FastAPI on dedicated E2E port `8012` was unavailable, so HTTP/auth/register cases failed, and the first run included stale UI selectors. Those assistant, visual lesson, and Feature 4 UI cases were updated and their targeted suites subsequently passed; the full suite was not rerun after those updates.
- Screenshots: **30** generated in `captures/`.
- Frontend unit tests: **154 passed, 0 failed**.
- Production build: passed. Vite still reports the existing Three.js and main bundle chunks over 500 kB.
- `git diff --check`: passed.

## Visual differences and limits

This is not a pixel-exact reproduction. The existing React route structure and feature APIs were preserved; some screens still use their established component layouts and differ from the contact sheet in artwork, text density, typography, card proportions, and exact spacing. The house SVG is a code-native approximation, not a copy of the reference picture. The scheduler uses existing account deadlines and browser/LiveKit call contracts; unavailable provider states remain visible inside expanded controls. OAuth buttons are labeled demos and do not authenticate. Browser captures use test fixtures and prove rendering/interaction only, not live Gemini, Gnani, LiveKit, telephony, or Windows desktop operation.
