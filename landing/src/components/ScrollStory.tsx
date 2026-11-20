import { useEffect, useRef, useState } from 'react';
import { ExampleMode } from '../data/debateData';
import { getWorkspaceUrl } from '../config';
import { EXPLORATION_ENTER_END, EXPLORATION_ENTER_START, introMotion } from './storyTimeline';

interface ScrollStoryProps {
  storyProgressRef: React.MutableRefObject<number>;
  postProgressRef: React.MutableRefObject<number>;
  onJumpToExampleTurn: (turnId: number, mode?: ExampleMode) => void;
  reducedMotion: boolean;
}

const CENTER_HEADLINE = [
  'Two Minds Speaking.',
  'Every Argument',
  'Mapped in Context.',
];

const INTRO_DESCRIPTION =
  'Follow claims, responses and questions in context, with a transcript you can revisit.';

const ACCOUNTING_WORDS =
  'Select a highlighted moment to inspect the words around it.'.split(' ');

const HOTSPOTS = [
  {
    id: 'hs-1',
    turnId: 1,
    mode: 'argument-trail' as ExampleMode,
    left: '14%',
    top: '57%',
    label: 'Claim · Turn 01',
    value: 'Uniforms reduce pressure',
  },
  {
    id: 'hs-2',
    turnId: 2,
    mode: 'argument-trail' as ExampleMode,
    left: '34%',
    top: '40%',
    label: 'Rebuttal · Turn 02',
    value: 'May challenge turn 01',
  },
  {
    id: 'hs-3',
    turnId: 4,
    mode: 'attack' as ExampleMode,
    left: '70%',
    top: '64%',
    label: 'Personal remark',
    value: 'Turn 04 · Review context',
  },
  {
    id: 'hs-4',
    turnId: 6,
    mode: 'drift' as ExampleMode,
    left: '82%',
    top: '44%',
    label: 'Topic drift',
    value: 'Turns 06–07 off-topic',
  },
];

const STATION_FEATURES = [
  { num: '01', text: 'Automatic A/B speaker attribution' },
  { num: '02', text: 'Possible personal-attack alerts' },
  { num: '03', text: 'Sustained topic-drift tracking' },
  { num: '04', text: 'Suggested argument trail & links' },
  { num: '05', text: 'Local SQLite & JSONL exports' },
];

const SPARKLINE_POINTS = '0,60 30,54 60,56 90,42 120,45 150,28 180,22 214,10';

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

function seg(p: number, a: number, b: number): number {
  return clamp01((p - a) / (b - a));
}

function easeCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function ScrollStory({
  storyProgressRef,
  postProgressRef,
  onJumpToExampleTurn,
  reducedMotion,
}: ScrollStoryProps) {
  const storyRef = useRef<HTMLElement | null>(null);
  const pointerTargetRef = useRef({ x: 0, y: 0 });
  const pointerSmoothRef = useRef({ x: 0, y: 0 });
  const sparkRef = useRef<SVGPolylineElement | null>(null);
  const [sparkLen, setSparkLen] = useState(260);

  const introRef = useRef<HTMLDivElement | null>(null);
  const heroCopyRef = useRef<HTMLDivElement | null>(null);
  const fogRef = useRef<HTMLDivElement | null>(null);
  const l3Ref = useRef<HTMLDivElement | null>(null);
  const acctWordRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const hotspotRefs = useRef<(HTMLDivElement | null)[]>([]);
  const l4Ref = useRef<HTMLDivElement | null>(null);
  const credRef = useRef<HTMLDivElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const countRef = useRef<HTMLSpanElement | null>(null);
  const featRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const progBarRef = useRef<HTMLDivElement | null>(null);

  const [activeHotspot, setActiveHotspot] = useState<string | null>('hs-3');
  const [activeFeat, setActiveFeat] = useState<number>(0);

  useEffect(() => {
    if (sparkRef.current) {
      setSparkLen(sparkRef.current.getTotalLength());
    }
  }, []);

  useEffect(() => {
    const onPointerMove = (e: PointerEvent) => {
      pointerTargetRef.current.x = e.clientX / window.innerWidth - 0.5;
      pointerTargetRef.current.y = e.clientY / window.innerHeight - 0.5;
    };
    window.addEventListener('pointermove', onPointerMove, { passive: true });

    let sp = 0;
    let lastTime = performance.now();
    let rafId = 0;

    const tick = (now: number) => {
      const dt = Math.max(0, Math.min(64, now - lastTime));
      lastTime = now;

      const story = storyRef.current;
      let rawP = 0;
      let rawPost = 0;
      if (story) {
        const rect = story.getBoundingClientRect();
        const scrollable = Math.max(1, story.offsetHeight - window.innerHeight);
        rawP = clamp01(-rect.top / scrollable);

        const pastStory = Math.max(0, -rect.top - scrollable);
        const totalPost = Math.max(
          1,
          document.documentElement.scrollHeight - window.innerHeight - scrollable,
        );
        rawPost = clamp01(pastStory / totalPost);
      }

      if (reducedMotion) {
        sp = rawP;
      } else {
        const alpha = 1 - Math.pow(0.86, dt / 16.7);
        sp += (rawP - sp) * alpha;
        if (Math.abs(rawP - sp) < 0.0002) sp = rawP;
      }

      storyProgressRef.current = sp;
      postProgressRef.current = rawPost;

      const pt = pointerTargetRef.current;
      const ps = pointerSmoothRef.current;
      ps.x += (pt.x - ps.x) * (reducedMotion ? 1 : 0.06);
      ps.y += (pt.y - ps.y) * (reducedMotion ? 1 : 0.06);
      const sx = reducedMotion ? 0 : ps.x;
      const sy = reducedMotion ? 0 : ps.y;

      if (progBarRef.current) {
        progBarRef.current.style.transform = `scaleX(${sp})`;
      }

      // One opening chapter: all text, speaker labels and controls share this exit.
      const intro = introMotion(sp, reducedMotion);
      if (introRef.current) {
        introRef.current.style.opacity = `${intro.opacity.toFixed(3)}`;
        introRef.current.style.visibility = intro.visible ? 'visible' : 'hidden';
        introRef.current.style.transform = `translate3d(0, ${intro.translateY.toFixed(2)}px, 0)`;
        introRef.current.inert = !intro.visible;
      }
      if (heroCopyRef.current) {
        heroCopyRef.current.style.transform = `translate3d(${(-sx * 10).toFixed(2)}px, ${(-sy * 6).toFixed(2)}px, 0)`;
      }

      // Subtle ivory cushion behind Beat 3 copy
      const fgIn = easeCubic(seg(sp, 0.38, 0.47));
      const fgOut = seg(sp, 0.65, 0.74);
      const fgOp = fgIn * (1 - fgOut);
      if (fogRef.current) {
        fogRef.current.style.visibility = fgOp <= 0.005 ? 'hidden' : 'visible';
        fogRef.current.style.opacity = `${fgOp.toFixed(3)}`;
        fogRef.current.style.transform = `translate3d(${((fgIn - 1) * 16 + sx * -8).toFixed(2)}vw, ${(sy * -6).toFixed(2)}px, 0)`;
      }

      // Explore a source moment as the unified introduction exits.
      const aIn = seg(sp, EXPLORATION_ENTER_START, EXPLORATION_ENTER_END);
      const aOut = seg(sp, 0.63, 0.69);
      const aVis = aIn > 0 && aOut < 1;
      if (l3Ref.current) {
        l3Ref.current.inert = !aVis;
        l3Ref.current.style.opacity = aVis ? '1' : '0';
        l3Ref.current.style.visibility = aVis ? 'visible' : 'hidden';
      }
      if (aVis) {
        const count = ACCOUNTING_WORDS.length;
        acctWordRefs.current.forEach((el, i) => {
          if (!el) return;
          const k = clamp01(aIn * 2.2 - (i / count) * 1.2);
          el.style.opacity = `${((0.15 + 0.85 * k) * (1 - aOut)).toFixed(3)}`;
          el.style.filter = `blur(${((1 - k) * 5 + aOut * 9).toFixed(2)}px)`;
        });

        hotspotRefs.current.forEach((el, i) => {
          if (!el) return;
          const k = seg(sp, 0.42 + i * 0.02, 0.46 + i * 0.02);
          const sc = k * (1 - aOut);
          el.style.visibility = sc <= 0.01 ? 'hidden' : 'visible';
          el.style.transform = `translate3d(${(sx * -22).toFixed(2)}px, ${(sy * -16).toFixed(2)}px, 0) scale(${sc.toFixed(3)})`;
        });
      }

      // Beat 4 Moderator Station: Tilting Telemetry Card + Sparkline + 5-Row Switcher (L4)
      const sIn = seg(sp, 0.71, 0.82);
      const l4Vis = sIn > 0;
      if (l4Ref.current) {
        l4Ref.current.style.visibility = l4Vis ? 'visible' : 'hidden';
      }
      if (l4Vis) {
        if (credRef.current) {
          credRef.current.style.opacity = `${sIn.toFixed(3)}`;
          credRef.current.style.transform = `translate3d(0, ${((1 - sIn) * 30).toFixed(2)}px, 0)`;
          credRef.current.style.filter = `blur(${((1 - sIn) * 8).toFixed(2)}px)`;
        }

        const cIn = easeCubic(seg(sp, 0.74, 0.86));
        if (cardRef.current) {
          cardRef.current.style.opacity = `${cIn.toFixed(3)}`;
          cardRef.current.style.transform = `perspective(900px) translate3d(${(sx * -14).toFixed(2)}px, ${((1 - cIn) * 60 + sy * -10).toFixed(2)}px, 0) rotateY(${(sx * 8).toFixed(2)}deg) rotateX(${(-sy * 8).toFixed(2)}deg)`;
        }

        if (countRef.current) {
          const val = Math.round(58 * seg(sp, 0.76, 0.9));
          countRef.current.textContent = String(val);
        }

        if (sparkRef.current) {
          const drawT = seg(sp, 0.77, 0.92);
          sparkRef.current.style.strokeDasharray = `${sparkLen}`;
          sparkRef.current.style.strokeDashoffset = `${(sparkLen * (1 - drawT)).toFixed(2)}`;
        }

        featRefs.current.forEach((el, i) => {
          if (!el) return;
          const k = easeCubic(seg(sp, 0.76 + i * 0.024, 0.82 + i * 0.024));
          el.style.opacity = `${k.toFixed(3)}`;
          el.style.transform = `translateX(${((1 - k) * 40).toFixed(2)}px)`;
        });
      }

      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('pointermove', onPointerMove);
    };
  }, [reducedMotion, sparkLen, storyProgressRef, postProgressRef]);

  return (
    <section
      id="top"
      ref={storyRef}
      aria-label="Interactive debate story"
      className="relative h-[380vh] bg-transparent"
    >
      <div className="sticky top-0 h-screen overflow-hidden bg-transparent">
        {/* Subtle lavender-pearl cushion behind Beat 3 paragraph */}
        <div
          ref={fogRef}
          className="pointer-events-none absolute"
          style={{
            left: '-8vw',
            top: '-6vh',
            width: '56vw',
            height: '62vh',
            visibility: 'hidden',
            WebkitMaskImage:
              'radial-gradient(ellipse 52% 48% at 46% 46%, #000 44%, rgba(0,0,0,.7) 64%, transparent 100%)',
            maskImage:
              'radial-gradient(ellipse 52% 48% at 46% 46%, #000 44%, rgba(0,0,0,.7) 64%, transparent 100%)',
          }}
          aria-hidden="true"
        >
          <div
            className="absolute inset-0 blur-[14px]"
            style={{
              background:
                'radial-gradient(60% 55% at 40% 45%, rgba(252,251,254,0.95), rgba(243,239,251,0.78) 60%, rgba(243,239,251,0.22))',
            }}
          />
        </div>

        {/* One continuous introduction: headline, context, speakers and actions. */}
        <div ref={introRef} className="pointer-events-none absolute inset-0 z-20" data-story-chapter="intro">
          <div className="intro-enter-surface absolute inset-0">
            <div ref={heroCopyRef} className="pointer-events-none absolute inset-0">
              <div className="pointer-events-auto absolute left-0 right-0 top-[11vh] px-4 text-center sm:top-[10.5vh]">
                <span className="chip-lavender">Human-led debate intelligence · English</span>
                <h1
                  className="mx-auto mt-3.5 max-w-xl text-[clamp(32px,4.2vw,64px)] font-medium leading-[0.98] tracking-[-0.04em] text-[#1E1934]"
                  style={{ textShadow: '0 2px 24px rgba(255,255,255,0.98), 0 0 12px rgba(255,255,255,0.94)' }}
                >
                  Two Voices. One Clear Trail.
                </h1>
              </div>
              <div className="intro-centered-copy pointer-events-auto absolute left-1/2 top-[53%] w-[min(840px,90vw)] -translate-x-1/2 -translate-y-1/2 text-center">
                <span className="chip-lavender">Between two perspectives</span>
                <h2
                  className="intro-centered-headline my-4 text-[clamp(34px,4.8vw,70px)] font-medium leading-[1.02] tracking-[-0.04em] text-[#1E1934]"
                  style={{ textShadow: '0 4px 28px rgba(252,251,254,0.95)' }}
                >
                  {CENTER_HEADLINE.map((line, index) => (
                    <span key={line} className="block">
                      {line}{index < CENTER_HEADLINE.length - 1 ? ' ' : ''}
                    </span>
                  ))}
                </h2>
                <p
                  className="mx-auto max-w-[440px] text-[13px] leading-[1.6] text-[#524B6B] sm:text-[15px]"
                  style={{ textShadow: '0 2px 18px rgba(252,251,254,0.98)' }}
                >
                  {INTRO_DESCRIPTION}
                </p>
              </div>
            </div>

          {/* Original wireframe speaker labels. */}
          {(['A', 'B'] as const).map((speaker, index) => (
            <div
              key={speaker}
              className={`pointer-events-none absolute top-[69%] z-20 hidden rounded-[12px] border bg-white/92 px-3.5 py-2.5 shadow-[0_12px_32px_rgba(30,25,52,0.09)] lg:block ${index === 0 ? 'left-[3.5%] border-[#6F5AC4]/30' : 'right-[3.5%] border-[#D87098]/32'}`}
              aria-hidden="true"
            >
              <div className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${index === 0 ? 'bg-[#6F5AC4]' : 'bg-[#D87098]'}`} />
                <span className="font-mono-data text-[10.5px] font-medium uppercase tracking-[0.14em] text-[#1E1934]">
                  Speaker {speaker} · Mesh 0{index + 1}
                </span>
              </div>
              <div className="mt-1.5 flex items-end gap-1">
                {[8, 14, 10, 16].map((barHeight, bar) => <span key={bar} className={`w-1 rounded-full ${index === 0 ? 'bg-[#6F5AC4]/75' : 'bg-[#D87098]/75'}`} style={{ height: barHeight }} />)}
                <span className="font-mono-data ml-1.5 text-[10px] text-[#524B6B]">
                  {index === 0 ? 'Claim · Turn 01' : 'Rebuttal · Turn 02'}
                </span>
              </div>
            </div>
          ))}

            <div className="pointer-events-none absolute left-1/2 top-[76%] hidden -translate-x-1/2 text-center sm:block">
              <p className="font-mono-data text-[8px] uppercase tracking-[0.2em] text-[#9B8CA8]">
                Scripted voice exchange
              </p>
            </div>

            {/* Primary actions stay available throughout the unified introduction. */}
            <div
              className="pointer-events-auto absolute bottom-[68px] left-[18px] right-[18px] max-w-md sm:bottom-[34px] sm:left-[34px] sm:right-auto"
            >
              <div className="mt-4 flex flex-wrap items-center gap-2.5">
                <a
                  href={getWorkspaceUrl('home')}
                  className="btn-primary inline-flex min-h-[40px] items-center gap-2 whitespace-nowrap rounded-[9px] px-4 py-2 text-xs font-medium"
                >
                  <span>Open workspace</span>
                  <span aria-hidden="true">→</span>
                </a>
                <a
                  href="#example"
                  className="btn-secondary inline-flex min-h-[40px] items-center whitespace-nowrap rounded-[9px] px-4 py-2 text-xs font-medium"
                >
                  Try interactive debate
                </a>
              </div>
            </div>

            {/* Bottom-Right Scroll Hint */}
            <div
              className="pointer-events-none absolute bottom-[24px] right-[18px] flex items-center gap-2.5 sm:bottom-[36px] sm:right-[34px]"
            >
              <span className="font-mono-data rounded-md border border-[#D4D9E6]/85 bg-white/90 px-2.5 py-0.5 text-[11px] uppercase tracking-[0.16em] text-[#524B6B]">
                Scroll into the dialogue
              </span>
              <span className="flex h-5 w-5 items-center justify-center rounded-full border border-[#6F5AC4]/45 bg-white/92 text-[#604CB5]">
                <span className="animate-nudge text-[11px] leading-none">⌄</span>
              </span>
            </div>
        </div>
        </div>

        {/* ============================================================== */}
        {/* SOURCE EXPLORATION — CONTEXT AND FOUR INSPECTION POINTS      */}
        {/* ============================================================== */}
        <div
          ref={l3Ref}
          className="pointer-events-none absolute inset-0 z-20"
          style={{ visibility: 'hidden' }}
        >
          <p
            className="pointer-events-none absolute left-[18px] top-[14vh] w-[min(560px,88vw)] text-[clamp(20px,1.95vw,29px)] font-normal leading-[1.18] tracking-[-0.02em] text-[#1E1934] sm:left-[34px]"
            style={{ textShadow: '0 2px 20px rgba(252,251,254,0.95)' }}
          >
            {ACCOUNTING_WORDS.map((word, i) => (
              <span
                key={`${word}-${i}`}
                ref={(el) => {
                  acctWordRefs.current[i] = el;
                }}
                className="mr-[0.24em] inline-block"
              >
                {word}
              </span>
            ))}
          </p>

          {HOTSPOTS.map((hs, i) => {
            const isOn = activeHotspot === hs.id;
            return (
              <div
                key={hs.id}
                ref={(el) => {
                  hotspotRefs.current[i] = el;
                }}
                style={{ left: hs.left, top: hs.top }}
                className="pointer-events-auto absolute -translate-x-1/2 -translate-y-1/2"
              >
                <div className="group flex flex-col items-start gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setActiveHotspot((prev) => (prev === hs.id ? null : hs.id))
                    }
                    className="hotspot-ring relative flex h-[24px] w-[24px] items-center justify-center rounded-full bg-[#6F5AC4] text-white transition-transform duration-200 hover:scale-110"
                    aria-expanded={isOn}
                    aria-label={`${hs.label}: ${hs.value}`}
                  >
                    <span className="h-[1.5px] w-[10px] bg-white" />
                    <span
                      className={`absolute h-[10px] w-[1.5px] bg-white transition-transform duration-200 ${
                        isOn ? 'scale-y-0' : 'scale-y-100'
                      }`}
                    />
                  </button>

                  <div className="rounded-[6px] border border-[#D4D9E6] bg-white/95 px-2.5 py-1.5 shadow-[0_10px_28px_rgba(30,25,52,0.1)]">
                    <div className="font-mono-data text-[10.5px] uppercase tracking-[0.14em] text-[#1E1934]">
                      {hs.label}
                    </div>
                    <div
                      className={`overflow-hidden transition-all duration-300 ${
                        isOn
                          ? 'mt-1 max-h-14 opacity-100'
                          : 'max-h-0 opacity-0 group-hover:mt-1 group-hover:max-h-14 group-hover:opacity-100'
                      }`}
                    >
                      <div className="text-xs font-medium text-[#5845A8]">
                        {hs.value}
                      </div>
                      <button
                        type="button"
                        onClick={() => onJumpToExampleTurn(hs.turnId, hs.mode)}
                        className="font-mono-data mt-0.5 text-[10px] uppercase tracking-[0.12em] text-[#1E1934] underline decoration-[#6F5AC4]/65 underline-offset-2 hover:text-[#604CB5]"
                      >
                        Inspect Turn 0{hs.turnId} →
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* ============================================================== */}
        {/* LAYER L4 — MODERATOR COCKPIT: PARTICIPATION CARD + 5 PILLARS   */}
        {/* ============================================================== */}
        <div
          ref={l4Ref}
          className="pointer-events-none absolute inset-0 z-20"
          style={{ visibility: 'hidden' }}
        >
          <div
            ref={credRef}
            className="pointer-events-none absolute left-[18px] top-[12vh] max-w-[380px] sm:left-[34px] sm:top-[13vh]"
          >
            <span className="chip-lavender mb-3">✕ Moderator station</span>
            <h2
              className="text-[clamp(22px,2.1vw,31px)] font-medium leading-[1.1] tracking-[-0.025em] text-[#1E1934]"
              style={{ textShadow: '0 2px 20px rgba(252,251,254,0.95)' }}
            >
              See how the conversation is shared
            </h2>
          </div>

          <div
            ref={cardRef}
            className="pearl-card-surface pointer-events-auto absolute bottom-[7vh] left-[18px] w-[225px] rounded-[14px] p-4 sm:bottom-auto sm:left-[36%] sm:top-[37vh] sm:w-[258px] sm:p-[18px]"
          >
            <h3 className="text-[15px] font-medium leading-tight text-[#1E1934]">
              Speaker A speaking
              <br />
              participation share
            </h3>
            <p className="font-mono-data mt-1 text-[9.5px] uppercase tracking-[0.12em] text-[#787192]">
              Illustrative · Turn 01–07
            </p>

            <div className="mt-3 flex items-baseline gap-1.5">
              <span
                ref={countRef}
                className="font-mono-data text-[44px] font-medium leading-none tracking-[-0.04em] text-[#1E1934]"
              >
                0
              </span>
              <span className="font-mono-data text-[11px] text-[#787192]">
                % share
              </span>
            </div>

            <span className="chip-lavender absolute right-4 top-[96px]">
              B: 42% (1:08)
            </span>

            <svg
              viewBox="0 0 220 70"
              className="mt-4 h-[64px] w-full overflow-visible"
              aria-hidden="true"
            >
              <polyline
                ref={sparkRef}
                fill="none"
                stroke="#6F5AC4"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={SPARKLINE_POINTS}
              />
              <circle cx="90" cy="42" r="2.6" fill="#C4CADA" />
              <circle cx="150" cy="28" r="2.6" fill="#D87098" />
              <circle cx="214" cy="10" r="3.6" fill="#604CB5" />
            </svg>

            <div className="font-mono-data mt-1 flex justify-between text-[9.5px] uppercase tracking-[0.14em] text-[#787192]">
              <span>T1</span>
              <span>T3</span>
              <span>T5</span>
              <span>T7</span>
            </div>
          </div>

          <div className="pearl-card-surface pointer-events-auto absolute bottom-[7vh] right-[18px] w-[46vw] max-w-[400px] rounded-[14px] px-3.5 py-1.5 sm:bottom-auto sm:right-[34px] sm:top-[30vh] sm:w-[min(400px,36vw)] sm:px-4">
            {STATION_FEATURES.map((feat, idx) => {
              const isOn = activeFeat === idx;
              return (
                <button
                  key={feat.num}
                  ref={(el) => {
                    featRefs.current[idx] = el;
                  }}
                  type="button"
                  onClick={() => setActiveFeat(idx)}
                  className={`grid w-full grid-cols-[28px_1fr_16px] items-center gap-2 py-2.5 text-left transition-all duration-200 ${
                    idx < STATION_FEATURES.length - 1
                      ? 'border-b border-[#D4D9E6]/70'
                      : ''
                  } ${
                    isOn
                      ? 'pl-1.5 text-[#5845A8]'
                      : 'text-[#524B6B] hover:pl-1.5 hover:text-[#5845A8]'
                  }`}
                >
                  <span className="font-mono-data text-[10.5px] opacity-60">
                    {feat.num}
                  </span>
                  <span className="font-mono-data text-[10px] uppercase tracking-[0.11em] sm:text-[11px]">
                    {feat.text}
                  </span>
                  <span
                    className={`hidden text-xs transition-transform duration-200 sm:inline-block ${
                      isOn ? 'translate-x-1 text-[#D87098]' : ''
                    }`}
                    aria-hidden="true"
                  >
                    →
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Bottom Progress Hairline */}
        <div
          className="pointer-events-none absolute bottom-[18px] left-1/2 z-30 h-[2px] w-[120px] -translate-x-1/2 overflow-hidden rounded-full bg-[#D4D9E6]/85"
          aria-hidden="true"
        >
          <div
            ref={progBarRef}
            className="h-full w-full origin-left bg-[#6F5AC4]"
            style={{ transform: 'scaleX(0)' }}
          />
        </div>
      </div>
    </section>
  );
}
