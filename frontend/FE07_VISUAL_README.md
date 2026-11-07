# FE-07 + ADV-04 — Interactive Visual Lesson Studio

## Existing session lesson

The protected `/visual` route remains connected to the authenticated learning session. It retains the Dijkstra shortest-path and equivalent-fractions demos, language preference, session navigation, and local quiz feedback.

## ADV-04 smartboard studio

Choose **Smartboard** in `/visual` to open the responsive, dark classroom workspace. Its SVG canvas uses a fixed 1000 × 620 viewBox, so the board keeps its coordinates across screen sizes. It supports pointer and touch drawing, object selection and dragging, highlighting, erasing, pan, zoom, undo/redo, reset, labels, circles, rectangles, and right-triangle diagrams. Lesson objects and student drawings are separate in memory. Keyboard users can tab to tools, activate diagram objects, use Delete to remove a selected object, Ctrl/Cmd+Z and Ctrl/Cmd+Y for history, and arrow keys to move selected objects or navigate lesson steps when no object is selected. Reduced-motion preferences disable the board pulse animation.

Three guided sample lessons include the Pythagorean theorem, solar-system order, and Telugu–English greeting vocabulary. Each lesson has step-by-step playback and an interactive check with immediate local feedback. Lesson playback is deterministic and can be paused, moved backward, or replayed.

## Integration contract

`src/lessonEngine.ts` exports the typed `LessonPlan`, discriminated `LessonCommand` union, runtime `validateLessonPlan`, and versioned `LessonPlanEnvelope` validation. A future RAG service can provide a plan envelope after validation. `TeacherGestureIntent` defines point, open-palm, and emphasize cues against lesson object IDs as a future boundary only. There is no avatar, live transport, or real-time synchronization implementation in ADV-04.

## Verification

Run from `frontend`:

```cmd
npm test
npm run build
npm run test:e2e -- e2e/visual-smartboard.spec.ts
```

ADV-04 verification: all 15 frontend unit/component-render tests pass; the TypeScript production build succeeds; the browser E2E passes against the production preview with mocked session APIs. The E2E performs lesson selection and playback, object explanation selection, pointer drawing, undo/redo, quiz feedback, and switching to a second lesson. It uses no backend database or student data.

## Limits

- Student drawings and board edits are browser-session state only; they are not saved to the backend.
- The current RAG and gesture interfaces are contracts only. No ADV-03 endpoint is assumed or called.
- Full-screen support depends on the browser's Fullscreen API.
- Browser E2E mocks the authenticated session responses, so it does not verify a live backend deployment.
