import { useEffect, useRef, useState } from 'react';
import { LoginModal } from './components/LoginModal';
import { Navbar } from './components/Navbar';
import { PearlCanvas, SceneInteractiveState } from './components/PearlCanvas';
import { PostScrollSections } from './components/PostScrollSections';
import { ScriptedExample } from './components/ScriptedExample';
import { ScrollStory } from './components/ScrollStory';
import { ExampleMode, SCRIPTED_TURNS } from './data/debateData';

export default function App() {
  const [exampleMode, setExampleMode] = useState<ExampleMode>('attack');
  const [highlightedTurnId, setHighlightedTurnId] = useState<number | null>(4);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);

  const storyProgressRef = useRef(0);
  const postProgressRef = useRef(0);
  const sceneStateRef = useRef<SceneInteractiveState>({
    activeMode: 'attack',
    activeTurnId: 4,
    activeSpeaker: 'B',
  });

  useEffect(() => {
    const matchedTurn = SCRIPTED_TURNS.find((t) => t.id === highlightedTurnId);
    sceneStateRef.current = {
      activeMode: exampleMode,
      activeTurnId: highlightedTurnId,
      activeSpeaker: matchedTurn ? matchedTurn.speaker : null,
    };
  }, [exampleMode, highlightedTurnId]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const syncPreference = () => setReducedMotion(mediaQuery.matches);
    syncPreference();

    mediaQuery.addEventListener('change', syncPreference);
    return () => mediaQuery.removeEventListener('change', syncPreference);
  }, []);

  const handleJumpToExampleTurn = (
    turnId: number,
    mode?: ExampleMode,
  ) => {
    if (mode) {
      setExampleMode(mode);
    }
    setHighlightedTurnId(turnId);
    const exampleSection = document.getElementById('example');
    if (exampleSection) {
      exampleSection.scrollIntoView({
        behavior: reducedMotion ? 'auto' : 'smooth',
      });
    }
  };

  return (
    <div className="relative min-h-screen bg-[#FCFBFE] text-[#1E1934]">
      {/* Persistent wireframe speakers and linked dialogue signals */}
      <div
        className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
        aria-hidden="true"
      >
        <div
          className="absolute inset-0 z-0"
          style={{
            background:
              'radial-gradient(54% 60% at 50% 48%, #FFFFFF 0%, #FBFAFE 48%, #F2EFF9 82%, #E7E3F3 100%)',
          }}
        />
        <div className="mesh-grid-bg pointer-events-none absolute inset-0 z-[1] opacity-85" />
        <PearlCanvas
          storyProgressRef={storyProgressRef}
          postProgressRef={postProgressRef}
          sceneStateRef={sceneStateRef}
          reducedMotion={reducedMotion}
          className="relative z-10 h-full w-full"
        />
      </div>

      <Navbar onOpenLogin={() => setLoginOpen(true)} />
      <main className="relative z-10">
        <ScrollStory
          storyProgressRef={storyProgressRef}
          postProgressRef={postProgressRef}
          onJumpToExampleTurn={handleJumpToExampleTurn}
          reducedMotion={reducedMotion}
        />
        <PostScrollSections
          exampleSection={
            <ScriptedExample
              mode={exampleMode}
              onModeChange={setExampleMode}
              highlightedTurnId={highlightedTurnId}
              onSelectTurn={setHighlightedTurnId}
              reducedMotion={reducedMotion}
            />
          }
        />
      </main>
      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
    </div>
  );
}
