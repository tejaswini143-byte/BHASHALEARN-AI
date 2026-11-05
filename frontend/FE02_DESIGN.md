# FE-02 — Premium Landing Page

## Implemented

- Responsive midnight navy, violet, cyan, and pink design system.
- Branded navigation and mobile menu.
- Hero with interactive microphone orb and animated waveform **visualization only** (not recording).
- Floating learning analytics preview cards.
- Clickable feature selection cards.
- Voice / visual / chat interactive preview tabs.
- Learning journey and closing call to action.
- React Router `/explore` placeholder page for future classroom.
- Accessible button labels, tab selection, reduced-motion handling, and mobile breakpoints.

## Test

From `frontend/` run:

```cmd
npm install
npm run build
npm run dev
```

Open http://localhost:5173. Check mobile navigation, orb toggle, feature selection, voice/visual/chat tabs, anchor navigation, and Explore route.

## Scope boundary

The voice orb, waveform, chart, and chat are UI previews. They do not record audio, evaluate pronunciation, stream AI responses, or represent real student metrics. Those functions belong to later frontend tasks and backend integration. Screenshots supplied by the user are design references, not copied branded assets.
