# Wireframe dialogue scene refinement

Restore the original page composition, quad-wire speakers, rose/pearl colors, grid, speaker badges and the small caption below the accepted speech sculpture. Do not use imported solid head sculptures or the replacement HTML diagram.

Faces retain their original rose/pearl materials, scale, facing direction and quad-wire identity. Build the surface on a 160 × 176 grid, drawing every second quad line. A shape-preserving Hermite height profile prevents overshoot around tight nose/lip landmarks. Smooth the temple/chin transition and nasal sidewalls; retain the mouth landmark that anchors the accepted speech sculpture.

Use an endpoint-preserving height distribution, with additional grid flow around eye sockets and mouth corners. Close the crown at its true apex and weld normals across the duplicate back seam. Fade the visible lattice gently at the crown and neck to avoid concentrated strokes while keeping facial lines legible.

Replace the detached solid eyes with almond-shaped wire contours, brow arcs and subtle nostril/ear/lip contours. These contours share the same jaw-hinge and eyelid deformation field as the skin and lattice. Jaw motion rotates rather than stretching the lower face. Recalculate normals when articulation or blinking changes, and skip unchanged frames. Reduced motion leaves the faces at rest. The speech sculpture, page layout, typography and colors stay unchanged.

The center is one continuous speech sculpture, not a collection of objects. Two satin ribbons with fine quad filaments taper exactly into both mouths and intertwine through a shared, slowly moving spatial phase. Violet and rose retain speaker attribution. A travelling light accent and a restrained speech inflection follow each speaker’s direction and smoothed activity. Their outlines and cross seams share the surface position buffer, so they stay registered throughout the animation. There are no bubbles, role icons, numbered medallions, ornaments or independent particles.

The geometry has fixed topology, capped amplitude and width, and smooth end envelopes. It is sampled without per-frame geometry allocation. The thin surface has a physical material; filament shaders carry directional light pulses along the same surface. Reduced motion freezes the shape and light travel while retaining the selected speaker’s emphasis. Surface normals are updated with the geometry, and the collapsed endpoint normals are inherited from neighboring rows. Both voices share one geometry score to avoid unrelated movement.

The former center HUD is replaced by a small unboxed caption below the sculpture: “Two voices. A shared thread.” with an explicit scripted-exchange label. Keep the original wireframe faces, speaker badges, hero copy and editorial content.

Keep the original scroll story and scripted inspection modes. Reduced-motion rendering must still respond to scroll, resize and selection changes. Dispose all geometry and materials.

Verification is limited to code, finite surface/normal data, monotone facial grids, crown/seam closure, contour deformation, bounded jaw motion, stable speech anchors, TypeScript and production build. No visual tests, as requested by the user.


## Unified opening chapter

Merge the initial hero and the former “Two Minds Speaking” vision scene into one introduction. Retain the upper H1, “Two Voices. One Clear Trail.”, and the large three-line center statement, “Two Minds Speaking. Every Argument Mapped in Context.”. Both live inside the same opening frame, with one contextual description: “Follow claims, responses and questions in context, with a transcript you can revisit.” Preserve the upper “Human-led debate intelligence · English” chip and the “Between two perspectives” chip above the center statement, using their existing lavender background, purple text and border colors. Keep the repeated “Two voices. A shared thread.” caption and the redundant three-line feature manifesto removed.

Both headings, the description, speaker labels and primary actions and scripted-exchange caption share one entry and one scroll-driven exit. Use `storyTimeline.ts` for the exit interval and the renderer’s hero speaker activity. Overlap the exit with source exploration so there is no empty beat or separate title reveal. The center statement is present from the initial frame and shares the same entry, pointer movement and exit as the upper text. Shorten the scroll story from 480vh to 380vh. Hidden controls become inert; hidden source overlays also become transparent to prevent explicitly visible children from leaking into the next chapter.

Give the later chapters distinct content: a short instruction to inspect a highlighted source moment, then participation review. Preserve navigation/action labels, product terms and transparency information where repetition serves usability. Keep the accepted speech-weave and face geometry unchanged. Validate the rendered markup and timeline programmatically; do not perform visual tests.
