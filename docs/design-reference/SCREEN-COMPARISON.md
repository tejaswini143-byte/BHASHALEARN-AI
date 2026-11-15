# Approved screen comparison inventory

Source: [`bhashalearn-15-screens.png`](./bhashalearn-15-screens.png). The source collage is cropped into the individual references under [`screens/`](./screens/).

This is a route and coverage inventory, not a claim of pixel-level visual acceptance. Current implementation uses a dark navy/cyan visual system in several feature pages while the approved collage uses a light lavender/purple student dashboard. No all-screen browser screenshot comparison has been completed in this integration run.

| # | Screen | Reference crop | Current route or state | Coverage in this run |
|---:|---|---|---|---|
| 1 | Login | `screens/01-login.png` | `/login` | Route present; auth E2E checks login and 401 handling |
| 2 | Registration | `screens/02-register.png` | `/register` | Route present; no live account was created |
| 3 | Forgot password | `screens/03-forgot-password.png` | Missing | No recovery route or backend recovery flow found |
| 4 | Student dashboard | `screens/04-dashboard.png` | `/dashboard` | Route present; protected redirect tested; authenticated data view not exercised |
| 5 | AI classroom | `screens/05-ai-classroom.png` | `/classroom`, `/voice` | Routes present; not live microphone/provider tested |
| 6 | AI chatbot | `screens/06-ai-chatbot.png` | `/chat` | Route present; live provider not tested |
| 7 | PDF Learning Studio | `screens/07-pdf-learning-studio.png` | `/documents`, `/knowledge-studio` | Routes present; no upload or provider-backed indexing in this run |
| 8 | My Courses | `screens/08-my-courses.png` | `/courses` | Route present; authenticated enrollment not exercised |
| 9 | Learning Timeline | `screens/09-learning-timeline.png` | Dashboard `#timeline`; `/progress-analytics` contains timeline | Embedded/combined; no dedicated timeline route |
| 10 | Progress Analytics | `screens/10-progress-analytics.png` | `/progress-analytics` | Route present; authenticated data not exercised |
| 11 | Settings | `screens/11-settings.png` | `/assistant` has assistant/reminder settings | Partial; no matching student profile settings screen |
| 12 | Mobile responsive | `screens/12-mobile-responsive.png` | Responsive states across routes | Narrow landing navigation E2E passed; no all-route mobile audit |
| 13 | Visual Lesson Studio | `screens/13-visual-lesson-studio.png` | `/visual-lessons`, `/visual` | Route present; feature 4 browser E2Es passed |
| 14 | Completion Certificate | `screens/14-certificate.png` | Missing | No certificate route/component found |
| 15 | LiveKit Calling | `screens/15-livekit-calling.png` | `/assistant` | Reminder/call surface present; no paid outbound call initiated |

## Browser evidence

- `frontend/tests/*.test.mjs`: 148 passed.
- Full Playwright suite: 75 passed, 8 skipped. The real HTTP student journey used the isolated local API; feature UI suites use their own mocked data and do not exercise external providers.
- Production build succeeds. The bundle warns that the Three.js/VRM chunks exceed 500 kB.

## Remaining design work

Implement the missing password recovery and certificate flows, split timeline/settings into the approved screens, then capture and compare all 15 routes at desktop and mobile sizes. Do not render static screenshots as page backgrounds.
