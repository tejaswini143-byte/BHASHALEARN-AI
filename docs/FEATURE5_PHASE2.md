# Feature 5 Phase 2 — Immersive rigged teacher

## Implemented in this branch
- Immersive classroom now accepts a locally selected .glb model and renders it through the existing animated teacher component.
- Non-GLB, empty, >25 MB and unrigged GLB uploads are rejected with visible errors.
- Replacing/removing the avatar disposes geometry, textures and materials.
- Avatar is held in browser memory only; it is not uploaded to a server.
- Classroom lesson controls and voice tutor remain available without a character.
- Added Phase 2 regression tests.

## Acceptance still required
- Run `npm ci --include=dev`, `npm test`, `npm run build`, and `npm run test:e2e` on a compatible environment.
- Manually test a rights-cleared humanoid GLB with animation clips, a skinned model without clips, invalid GLB bytes, 25 MB limit, replacing and removing avatars.
- Confirm gestures, facial blendshapes, voice-to-mouth timing, reduced motion, browser WebGL fallback, responsive layout and keyboard focus with the actual asset.
- This phase is **in progress**. No built-in realistic licensed human asset has been supplied. Rigged assets vary in skeleton/bone naming and animation conventions.
