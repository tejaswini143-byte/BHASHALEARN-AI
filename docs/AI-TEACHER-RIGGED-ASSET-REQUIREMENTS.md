# Rigged Human Teacher Asset Requirements

The current RC has no rigged full-body human teacher asset. A single photograph cannot provide hidden body surfaces, a consistent 3D profile, or facial motion from arbitrary viewpoints. The classroom must keep describing the existing photo as a local reference and must not present it as a walking avatar.

## Asset package required

- One human-character model in `.glb` (preferred) or `.gltf` format, with all geometry and textures included or locally referenced. A `.vrm` export is acceptable only if its runtime loader and license are approved for this project.
- Full-body, realistic female adult proportions, neutral standing pose, clean topology, and a documented real-world height/forward axis. Model should be optimized for a browser scene: target under 80,000 triangles and 2K textures, with a lower-detail LOD if the source is heavier.
- A deformable humanoid skeleton compatible with Three.js animation retargeting: hips/root, spine/chest/neck/head, bilateral clavicle/arm/forearm/hand, and leg/foot chains. Include a standard T-pose or A-pose and stable bone names/retarget map.
- Facial rig with jaw and eye controls plus phoneme/viseme blend shapes for at least `sil`, `aa`, `ee`, `oh`, `ou`, `fv`, `mbp`, `th`, `l`, and `rest`. A single open/close mouth slider is insufficient for accurate Telugu and English lip-sync.
- Animation clips with start/end markers and root-motion policy: idle/listen, explain with restrained upper-body gestures, point left/right/up, write on a board, turn toward board, turn back to student, and walk/stop/turn. Clips must blend without foot sliding; marker/pen prop attachment points must be specified if a prop is supplied.
- Materials, texture maps, and any props must be redistributable with the RC. Include creator, source URL, license name/version, attribution text, commercial/demo rights, and any likeness/model-release documentation.

## Integration and acceptance checks

1. Store the approved package under the RC's local teacher asset directory; do not upload a student's photo or generated likeness to an external service.
2. Validate the file, license record, skeleton map, animation names, bounds, and facial morph-target names in a local asset-check script before enabling it in the student UI.
3. Retarget animations to the classroom board/stage coordinate system and keep teacher, board, lesson step, and speech player on the same session clock.
4. Drive mouth shapes from provider-supplied, timestamped phoneme/viseme alignment when available. If only audio amplitude is available, label the mouth motion as approximate audio-reactive animation.
5. Test English and Telugu speech, pause/resume, interruption, lesson-step transitions, reduced motion, keyboard access, and WebGL fallback in the real browser.
6. Keep the photo teacher controls disabled for full-body claims until the model passes the checks above. Do not describe a static image, 2D cutout, or geometric mannequin as a realistic human avatar.

## Still needed from the project owner

Provide a properly licensed rigged model package (including source/license evidence) or authorize a named avatar provider and its data-processing terms. If the selected model is intended to resemble the supplied teacher, also provide documented likeness consent for that model and the permitted uses. A photograph alone is not an animation-ready asset.
