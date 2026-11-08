# INT-19 Holographic Teacher

## Feature boundary

`frontend/src/HolographicTeacher.tsx` is an isolated route component and reusable Three.js scene. It does not alter the immersive classroom, teacher preview, backend, or data model. The `/holographic-teacher` route is lazy loaded. The scene has a clearly labeled articulated hologram proxy because the verified baseline and ADV-05 worktree contain no licensed rigged character asset or license record. It must not be presented as photorealistic.

## Rendering and motion

React Three Fiber renders translucent cyan glass-like character materials, violet and cyan edge rings, classroom glass panels, volumetric-style layered light slits, and a point-particle field. The proxy has separate body, head, arm, gaze, blink, and mouth controls. Idle breathing/head gaze, timed blink, speaking mouth shapes, listening pose, thinking tilt, and pointing gesture use damped frame updates. Three.js materials are disposed on unmount. Low-performance mode lowers DPR, disables antialiasing, and reduces particles and light-ray layers. Reduced motion switches Canvas to demand rendering and stops procedural motion. WebGL fallback retains concept text and controls.

Floating lessons demonstrate a right-triangle construction and Pythagorean expression, a partitioned fraction circle, and nested planetary orbit lines with a gravity expression. Labels are spatial glass panels; there is no blackboard, smartboard, or projector.

## Voice and integration with INT10C

The component accepts a structural `HolographicVoiceSource` adapter and defaults to a silent source. INT10C's `immersiveVoiceBridge` matches this interface and can be passed as the `voiceSource` prop after merging. The latest `AvatarSyncFrame` media-clock timestamped viseme drives the mouth only while the source reports `speaking`; paused/interrupted/error states settle the proxy mouth. The INT10C bridge rejects stale generations. If there are no viseme/phoneme cues, the existing `AvatarSyncController` selects its explicitly approximate audio-driven mode. Telugu, English, and mixed language are carried in the shared frame by the existing contract. This verified baseline does not include INT10C's bridge; the completed INT10C/INT18B integration must pass the bridge and call `acceptFrame` for controller updates and `setState` for listening/thinking. The isolated feature does not call voice providers.

## Merge guidance after INT18B

Cherry-pick or merge INT-19 into the completed INT18B integration branch only after verifying the shared files. Keep `HolographicTeacher.tsx`, its CSS, and this document. Add the lazy `/holographic-teacher` route from `App.tsx` if INT18B has not already supplied a feature route, then connect the finalized INT10C `immersiveVoiceBridge` producer to `AvatarSyncController` frames. Preserve current `/immersive`, `/teacher`, `/voice`, and lesson routes. Resolve duplicate route or bridge changes manually; do not use INT18B as the INT19 starting point.

## Asset blocker

Before release as a realistic human teacher, obtain a female rigged GLB/VRM with an explicit redistribution/commercial-use license and attribution requirements. Verify its skinning, animation clips, eye/blink and viseme morphs, source URL, license text, and attribution in a separate reviewed asset change. No external asset was downloaded or assumed in INT-19.
