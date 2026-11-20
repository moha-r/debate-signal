/** Shared opening timeline for the copy, controls and speaker activity. */
export const INTRO_EXIT_START = 0.26;
export const INTRO_EXIT_END = 0.40;
export const EXPLORATION_ENTER_START = 0.38;
export const EXPLORATION_ENTER_END = 0.51;

export function introMotion(progress: number, reducedMotion: boolean) {
  const t = Math.max(0, Math.min(1, (progress - INTRO_EXIT_START) / (INTRO_EXIT_END - INTRO_EXIT_START)));
  const exit = t * t * (3 - 2 * t);
  return {
    opacity: 1 - exit,
    translateY: reducedMotion ? 0 : exit * -32,
    visible: t < 1,
  };
}
