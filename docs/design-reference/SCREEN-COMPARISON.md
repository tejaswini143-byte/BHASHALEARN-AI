# Approved 15-screen reference: implementation and visual evidence

Reference source: [`bhashalearn-15-screens.png`](./bhashalearn-15-screens.png), with the individual panel crops under [`screens/`](./screens/).

The React/Vite frontend is served from `frontend/` at `http://127.0.0.1:5211` in the isolated local acceptance setup. The refreshed browser captures are in the ignored local folder `.test-tmp/design-evidence/`; they show the real React routes, with fixture data for authenticated flows. They are evidence of rendered layout and navigation, not live provider or desktop acceptance.

| # | Reference screen | Current route/state | Current match and remaining difference |
|---:|---|---|---|
| 1 | Login | `/login` | Split lavender/navy auth panel with form and hand-drawn student illustration. Social sign-in in the reference is not connected to an OAuth provider. |
| 2 | Registration | `/register` | Same auth system, account creation, required password confirmation, and mismatch feedback. Illustration is an original SVG approximation. |
| 3 | Forgot password | `/forgot-password` | Reset request form is implemented; backend uses a non-disclosing reset response. |
| 4 | Student dashboard | `/dashboard` | Violet sidebar, light cards, real account-backed progress/session content, quick links, and timeline. The reference’s exact typography and illustrated course artwork are not reproduced. |
| 5 | AI classroom / voice | `/voice` and `/classroom` | Existing voice-learning flow retained and recolored to the violet/light palette. The original teacher artwork and live provider workflow were not part of this frontend-only acceptance run. |
| 6 | AI chatbot | `/chat` | Existing authenticated chat UI retained and restyled. No live Gemini request was made. |
| 7 | PDF Learning Studio | `/documents` and `/knowledge-studio` | Existing upload/library and knowledge workflows retained and moved to a light card palette. No upload/provider request was made. |
| 8 | My Courses | `/courses` | Existing course catalog and progress UI retained with light styling. |
| 9 | Learning Timeline | `/timeline` | Dedicated authenticated timeline route. Dashboard activity rows now use a two-line, timestamp-aligned layout. |
| 10 | Progress Analytics | `/progress-analytics` | Existing authenticated analytics retained with light cards and violet accents. |
| 11 | Settings | `/settings` | Dedicated profile/preferences settings route. |
| 12 | Mobile dashboard | Responsive `/dashboard` | Mobile layout was captured at 390 px; the page fits the viewport and has a fixed five-item bottom navigation. |
| 13 | Visual Lesson Studio | `/visual-lessons` | Existing interactive lesson controls retained. Its dark interactive smartboard and current lesson content differ from the reference’s illustrated house lesson. |
| 14 | Certificate | `/certificate` | Certificate is conditional on actual account/course completion; no fabricated completion state is shown. |
| 15 | Practice call scheduler | `/assistant` | Current route is the existing assistant/reminder surface. It does not match the reference’s LiveKit practice-call scheduler; LiveKit/SIP work was explicitly paused. |

## Browser evidence

- Captures: `.test-tmp/design-evidence/01-login.png` through `15-call-scheduler.png`; `04-dashboard.png`, `05-ai-classroom.png`, and `12-mobile-dashboard.png` were refreshed after the final layout adjustments.
- Frontend unit suite: **154 passed, 0 failed**.
- Targeted Playwright auth, dashboard navigation, settings, timeline, certificate, and password recovery suites: **15 passed, 1 skipped**. The skipped test requires configured dedicated account credentials. A separate Voice Studio wheel/keyboard scrolling check passed (**1 passed**).
- Production TypeScript/Vite build succeeded. Vite reports the existing large Three.js/vendor chunks (>500 kB after minification).
- No live Gemini, Prisma, LiveKit/SIP, Windows desktop, or outbound call acceptance is claimed in this frontend-only run.

## Remaining visual differences

The implementation applies the shared navy, lavender, and violet visual system to the existing functional React routes. Several routes remain approximations rather than pixel-level reproductions. In particular, the visual lesson illustration and call scheduler do not match the reference content, and OAuth sign-in buttons are not connected to providers. The reference image is not used as a page background; controls remain real React components.
