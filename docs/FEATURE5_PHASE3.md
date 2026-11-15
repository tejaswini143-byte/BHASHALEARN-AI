# Feature 5 — Phase 3: Voice-to-avatar synchronization

## Implemented
- Reuses VoiceTutor's existing GNANI/Timbre playback integration and HTML audio media-clock based AvatarSyncController. No duplicate audio playback engine or fabricated provider connection.
- Added conservative viseme mapping to common GLB morph targets (viseme, jawOpen, mouthFunnel, mouthPucker, mouthClose, tongueOut).
- Mouth shape updates on actual voice bridge frames; pause, interruption and error state changes notify the 3D renderer immediately to silence the mouth.
- Invalid playback clock frames and older generation frames are ignored.
- Regression tests cover speech morph mapping, silence on pause/interruption, and stale/invalid frames.

## Important limitations and manual testing
- If a GLB has no matching mouth blendshapes, facial lip movement will not appear even though the voice plays. Full retargeting requires a compatible rigged character.
- Timbre audio without timed phoneme/viseme metadata uses the existing approximate audio-driven mode. Do not claim accurate phoneme-level synchronization.
- Provider configuration and live GNANI voice tests require the user's local environment; no keys are stored in this branch.
- Run `npm test`, `npm run build`, and browser acceptance with a licensed rigged GLB. Verify Telugu/English voice, repeated play/pause/resume, interruption, malformed audio, no network, reduced motion, and GLB without morph targets.
- Phase 3 remains in progress until these checks pass.
