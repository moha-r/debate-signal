import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  FileText,
  GitBranch,
  Pause,
  Play,
  RotateCcw,
  ShieldAlert,
  X,
} from 'lucide-react';
import {
  DEBATE_QUESTION,
  ExampleMode,
  ILLUSTRATIVE_PARTICIPATION,
  SCRIPTED_TURNS,
} from '../data/debateData';

interface ScriptedExampleProps {
  mode: ExampleMode;
  onModeChange: (mode: ExampleMode) => void;
  highlightedTurnId: number | null;
  onSelectTurn: (turnId: number | null) => void;
  reducedMotion: boolean;
}

const EXAMPLE_TABS: { id: ExampleMode; label: string }[] = [
  { id: 'drift', label: 'Topic drift' },
  { id: 'attack', label: 'Personal attack' },
  { id: 'speaking-time', label: 'Speaking time' },
  { id: 'argument-trail', label: 'Argument trail' },
  { id: 'report', label: 'Session report' },
];

export function ScriptedExample({
  mode,
  onModeChange,
  highlightedTurnId,
  onSelectTurn,
  reducedMotion,
}: ScriptedExampleProps) {
  const [attackQueueStatus, setAttackQueueStatus] = useState<
    'pending' | 'reviewed' | 'dismissed'
  >('pending');
  const [driftQueueStatus, setDriftQueueStatus] = useState<
    'pending' | 'reviewed' | 'dismissed'
  >('pending');
  const [contextExpanded, setContextExpanded] = useState(false);
  const [verdict, setVerdict] = useState<'none' | 'correct' | 'incorrect'>('none');
  const [verdictReason, setVerdictReason] = useState('');
  const [savedNotice, setSavedNotice] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  const turnRefs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!highlightedTurnId) return;
    const node = turnRefs.current[highlightedTurnId];
    if (node) {
      node.scrollIntoView({
        behavior: reducedMotion ? 'auto' : 'smooth',
        block: 'nearest',
      });
    }
  }, [highlightedTurnId, reducedMotion]);

  const applyTurnContext = (turnId: number) => {
    onSelectTurn(turnId);
    if (turnId === 4) {
      onModeChange('attack');
    } else if (turnId === 6 || turnId === 7) {
      onModeChange('drift');
    } else {
      onModeChange('argument-trail');
    }
  };

  useEffect(() => {
    if (!isPlaying) return;
    const timer = window.setTimeout(() => {
      const current = highlightedTurnId ?? 0;
      const next = current >= SCRIPTED_TURNS.length ? 1 : current + 1;
      applyTurnContext(next);
    }, 2400);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying, highlightedTurnId]);

  const handleReset = () => {
    setIsPlaying(false);
    setAttackQueueStatus('pending');
    setDriftQueueStatus('pending');
    setContextExpanded(false);
    setVerdict('none');
    setVerdictReason('');
    setSavedNotice(false);
    onSelectTurn(null);
  };

  const focusTurn = (turnId: number) => {
    setIsPlaying(false);
    onSelectTurn(turnId);
  };

  const stepTurn = (delta: -1 | 1) => {
    setIsPlaying(false);
    const current = highlightedTurnId ?? (delta > 0 ? 0 : 2);
    const next = Math.min(
      SCRIPTED_TURNS.length,
      Math.max(1, current + delta),
    );
    applyTurnContext(next);
  };

  const isContextHighlighted = (turnId: number) => {
    if (mode === 'attack' && contextExpanded) {
      return turnId >= 3 && turnId <= 5;
    }
    if (mode === 'drift') {
      return turnId === 6 || turnId === 7;
    }
    if (mode === 'attack') {
      return turnId === 4;
    }
    if (mode === 'argument-trail') {
      return turnId >= 1 && turnId <= 3;
    }
    return false;
  };

  return (
    <section
      id="example"
      aria-labelledby="example-heading"
      className="relative z-20 border-t border-[#D4D9E6]/80 bg-transparent py-20 sm:py-24"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="flex flex-col justify-between gap-4 border-b border-[#D4D9E6]/80 pb-8 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="font-mono-data text-xs font-medium text-[#604CB5]">
              Scripted example · Interactive simulation
            </p>
            <h2
              id="example-heading"
              className="mt-2 text-3xl font-medium tracking-[-0.02em] text-[#1E1934] sm:text-4xl"
              style={{ textWrap: 'balance' }}
            >
              See how one debate unfolds across every signal.
            </h2>
            <p className="mt-3 text-base leading-relaxed text-[#524B6B]">
              Explore a pre-written seven-turn discussion without turning on
              your microphone. Step through turns below to watch the 3D faces
              and dialogue signals respond.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 self-start md:self-auto">
            <button
              type="button"
              onClick={() => {
                if (!isPlaying && !highlightedTurnId) {
                  applyTurnContext(1);
                }
                setIsPlaying((prev) => !prev);
              }}
              className="btn-primary inline-flex min-h-[40px] shrink-0 items-center gap-2 whitespace-nowrap rounded-[11px] px-4 py-2 text-xs font-medium"
            >
              {isPlaying ? (
                <>
                  <Pause className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Pause walkthrough</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Play 7-turn walkthrough</span>
                </>
              )}
            </button>

            <div className="inline-flex items-center rounded-[11px] border border-[#D4D9E6] bg-white/92 p-0.5 shadow-sm">
              <button
                type="button"
                onClick={() => stepTurn(-1)}
                aria-label="Previous scripted turn"
                className="inline-flex h-9 w-9 items-center justify-center rounded-[9px] text-[#524B6B] hover:bg-[#F3EFFB] hover:text-[#1E1934]"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>
              <span className="font-mono-data px-2 text-[11px] text-[#524B6B]">
                {highlightedTurnId ? `T0${highlightedTurnId}/07` : '07 turns'}
              </span>
              <button
                type="button"
                onClick={() => stepTurn(1)}
                aria-label="Next scripted turn"
                className="inline-flex h-9 w-9 items-center justify-center rounded-[9px] text-[#524B6B] hover:bg-[#F3EFFB] hover:text-[#1E1934]"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <button
              type="button"
              onClick={handleReset}
              className="btn-secondary inline-flex min-h-[40px] shrink-0 items-center gap-2 whitespace-nowrap rounded-[11px] px-3.5 py-2 text-xs font-medium"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Reset</span>
            </button>
          </div>
        </div>

        {/* Mode Tabs */}
        <div
          role="tablist"
          aria-label="Scripted example inspection modes"
          className="mt-7 flex flex-wrap gap-2"
        >
          {EXAMPLE_TABS.map((tab) => {
            const active = mode === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                type="button"
                aria-selected={active}
                onClick={() => {
                  setIsPlaying(false);
                  onModeChange(tab.id);
                  setContextExpanded(false);
                  if (tab.id === 'attack') onSelectTurn(4);
                  else if (tab.id === 'drift') onSelectTurn(6);
                  else if (tab.id === 'argument-trail') onSelectTurn(1);
                  else onSelectTurn(null);
                }}
                className={`min-h-[40px] whitespace-nowrap rounded-[11px] border px-4 py-2 text-sm font-medium transition-colors ${
                  active
                    ? 'border-[#6F5AC4] bg-[#6F5AC4] text-white shadow-[0_6px_18px_rgba(111,90,196,0.24)]'
                    : 'border-[#D4D9E6] bg-white/90 text-[#524B6B] hover:border-[#6F5AC4]/45 hover:bg-[#F3EFFB] hover:text-[#1E1934]'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Two-Column Interactive Workspace */}
        <div className="mt-6 grid items-start gap-6 lg:grid-cols-12">
          {/* LEFT: 7-Turn Scripted Transcript */}
          <div className="rounded-[18px] border border-[#D4D9E6]/90 bg-white/90 p-5 shadow-[0_18px_48px_rgba(30,25,52,0.05)] sm:p-6 lg:col-span-7">
            <div className="border-b border-[#D4D9E6]/80 pb-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono-data text-xs text-[#787192]">
                  Session question
                </span>
                <span className="font-mono-data text-xs text-[#787192]">
                  7 scripted turns · Static preview
                </span>
              </div>
              <h3 className="mt-1 text-lg font-medium text-[#1E1934]">
                {DEBATE_QUESTION}
              </h3>
            </div>

            <div className="mt-4 space-y-2.5">
              {SCRIPTED_TURNS.map((turn) => {
                const isExplicitFocus = highlightedTurnId === turn.id;
                const isModeHighlight = isContextHighlighted(turn.id);
                const isAttack = turn.flag === 'attack';
                const isDrift = turn.flag === 'drift';

                let cardStyle =
                  'border-[#D4D9E6]/80 bg-[#F3EFFB]/45 hover:border-[#6F5AC4]/45';
                if (isExplicitFocus) {
                  cardStyle =
                    'border-[#6F5AC4] bg-[#F3EFFB] ring-1 ring-[#6F5AC4]/25';
                } else if (isModeHighlight && isAttack) {
                  cardStyle = 'border-[#D87098]/60 bg-[#FDF4F8]';
                } else if (isModeHighlight && isDrift) {
                  cardStyle = 'border-[#8E7CC3]/55 bg-[#F3EFFB]';
                } else if (isModeHighlight) {
                  cardStyle = 'border-[#6F5AC4]/35 bg-[#F3EFFB]/90';
                }

                return (
                  <div
                    key={turn.id}
                    ref={(el) => {
                      turnRefs.current[turn.id] = el;
                    }}
                    tabIndex={0}
                    onClick={() => focusTurn(turn.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        focusTurn(turn.id);
                      }
                    }}
                    className={`cursor-pointer rounded-[11px] border p-3.5 transition-all ${cardStyle}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-xs">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{
                            backgroundColor:
                              turn.speaker === 'A' ? '#6F5AC4' : '#D87098',
                          }}
                          aria-hidden="true"
                        />
                        <span className="font-medium text-[#1E1934]">
                          {turn.speakerName}
                        </span>
                        <span className="font-mono-data text-[#787192]">
                          Turn {turn.turnNumber} · {turn.timestamp}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 text-xs">
                        {mode === 'argument-trail' && (
                          <span className="font-medium text-[#5845A8]">
                            {turn.role}
                            {turn.secondaryRole ? ` / ${turn.secondaryRole}` : ''}
                          </span>
                        )}
                        {isAttack && mode === 'attack' && (
                          <span className="flex items-center gap-1 font-medium text-[#B04B74]">
                            <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
                            Possible personal attack
                          </span>
                        )}
                        {isDrift && mode === 'drift' && (
                          <span className="flex items-center gap-1 font-medium text-[#5845A8]">
                            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
                            Topic drift
                          </span>
                        )}
                      </div>
                    </div>

                    <p className="mt-1.5 text-sm leading-relaxed text-[#383152]">
                      {turn.text}
                    </p>

                    {mode === 'argument-trail' && turn.linksToTurn && (
                      <div className="mt-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            focusTurn(turn.linksToTurn!);
                          }}
                          className="font-mono-data text-xs font-medium text-[#604CB5] underline decoration-[#6F5AC4]/45 underline-offset-2 hover:text-[#1E1934]"
                        >
                          {turn.linkLabel} → Jump to Turn 0{turn.linksToTurn}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* RIGHT: Contextual Inspector Panel */}
          <div className="space-y-4 lg:col-span-5">
            {mode === 'drift' && (
              <div className="rounded-[18px] border border-[#D4D9E6]/90 bg-white/88 p-5 shadow-[0_18px_48px_rgba(30,25,52,0.05)] sm:p-6">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-semibold text-[#1E1934]">
                    <AlertTriangle
                      className="h-4 w-4 text-[#604CB5]"
                      aria-hidden="true"
                    />
                    Topic drift observation
                  </span>
                  <span className="font-mono-data text-xs text-[#787192]">
                    Status: {driftQueueStatus}
                  </span>
                </div>

                <p className="mt-3 text-sm leading-relaxed text-[#524B6B]">
                  An alert appears after two consecutive turns are classified as
                  off-topic relative to{' '}
                  <span className="font-medium text-[#1E1934]">
                    “{DEBATE_QUESTION}”
                  </span>
                  . Repeated drift alerts are suppressed until the discussion
                  returns to the question.
                </p>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => focusTurn(6)}
                    className="rounded-lg border border-[#D4D9E6] bg-[#F3EFFB] px-3 py-1.5 text-xs font-medium text-[#1E1934] hover:border-[#6F5AC4]"
                  >
                    Highlight Turn 06
                  </button>
                  <button
                    type="button"
                    onClick={() => focusTurn(7)}
                    className="rounded-lg border border-[#D4D9E6] bg-[#F3EFFB] px-3 py-1.5 text-xs font-medium text-[#1E1934] hover:border-[#6F5AC4]"
                  >
                    Highlight Turn 07
                  </button>
                </div>

                <div className="mt-4 flex flex-wrap gap-2 border-t border-[#D4D9E6]/80 pt-4">
                  <button
                    type="button"
                    onClick={() => setDriftQueueStatus('reviewed')}
                    className={`inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${
                      driftQueueStatus === 'reviewed'
                        ? 'border-[#6F5AC4] bg-[#6F5AC4] text-white'
                        : 'border-[#D4D9E6] bg-white text-[#1E1934]'
                    }`}
                  >
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                    Reviewed
                  </button>
                  <button
                    type="button"
                    onClick={() => setDriftQueueStatus('dismissed')}
                    className={`inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${
                      driftQueueStatus === 'dismissed'
                        ? 'border-[#787192] bg-[#787192] text-white'
                        : 'border-[#D4D9E6] bg-white text-[#1E1934]'
                    }`}
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                    Dismissed
                  </button>
                </div>
              </div>
            )}

            {mode === 'attack' && (
              <div className="rounded-[18px] border border-[#D4D9E6]/90 bg-white/88 p-5 shadow-[0_18px_48px_rgba(30,25,52,0.05)] sm:p-6">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-semibold text-[#1E1934]">
                    <ShieldAlert
                      className="h-4 w-4 text-[#D87098]"
                      aria-hidden="true"
                    />
                    Possible personal attack · Turn 04
                  </span>
                  <span className="font-mono-data text-xs text-[#787192]">
                    Queue: {attackQueueStatus}
                  </span>
                </div>

                <p className="mt-3 text-sm leading-relaxed text-[#524B6B]">
                  Surfaces moments where phrasing shifts from debating ideas to
                  targeting a participant. Click{' '}
                  <strong className="font-medium text-[#1E1934]">
                    Review context
                  </strong>{' '}
                  to inspect Turns 03, 04, and 05 together.
                </p>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setContextExpanded((prev) => !prev);
                      focusTurn(4);
                    }}
                    className={`min-h-[38px] rounded-lg border px-3 py-1.5 text-xs font-medium ${
                      contextExpanded
                        ? 'border-[#D87098] bg-[#FDF4F8] text-[#B04B74]'
                        : 'border-[#D4D9E6] bg-[#F3EFFB] text-[#1E1934] hover:border-[#D87098]/70'
                    }`}
                  >
                    {contextExpanded
                      ? 'Showing context (Turns 03–05)'
                      : 'Review context (Turns 03–05)'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setAttackQueueStatus('reviewed')}
                    className={`inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${
                      attackQueueStatus === 'reviewed'
                        ? 'border-[#6F5AC4] bg-[#6F5AC4] text-white'
                        : 'border-[#D4D9E6] bg-white text-[#1E1934]'
                    }`}
                  >
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                    Reviewed
                  </button>
                  <button
                    type="button"
                    onClick={() => setAttackQueueStatus('dismissed')}
                    className={`inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${
                      attackQueueStatus === 'dismissed'
                        ? 'border-[#787192] bg-[#787192] text-white'
                        : 'border-[#D4D9E6] bg-white text-[#1E1934]'
                    }`}
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                    Dismissed
                  </button>
                </div>

                {/* Separate Alert Accuracy Assessment */}
                <div className="mt-5 border-t border-[#D4D9E6]/80 pt-4">
                  <p className="text-xs font-medium text-[#1E1934]">
                    Separate moderator assessment (saved locally for JSONL export)
                  </p>
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setVerdict('correct');
                        setSavedNotice(true);
                      }}
                      className={`min-h-[36px] rounded-lg border px-3 py-1.5 text-xs font-medium ${
                        verdict === 'correct'
                          ? 'border-[#6F5AC4] bg-[#F3EFFB] text-[#5845A8]'
                          : 'border-[#D4D9E6] bg-[#FCFBFE] text-[#524B6B]'
                      }`}
                    >
                      Alert is correct
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setVerdict('incorrect');
                        setSavedNotice(true);
                      }}
                      className={`min-h-[36px] rounded-lg border px-3 py-1.5 text-xs font-medium ${
                        verdict === 'incorrect'
                          ? 'border-[#D87098] bg-[#FDF4F8] text-[#B04B74]'
                          : 'border-[#D4D9E6] bg-[#FCFBFE] text-[#524B6B]'
                      }`}
                    >
                      Alert is incorrect
                    </button>
                  </div>

                  {verdict !== 'none' && (
                    <div className="mt-3 space-y-2">
                      <label htmlFor="example-reason" className="sr-only">
                        Optional assessment reason
                      </label>
                      <input
                        id="example-reason"
                        type="text"
                        value={verdictReason}
                        onChange={(e) => setVerdictReason(e.target.value)}
                        placeholder="Optional note (e.g., direct personal insult)"
                        className="w-full rounded-lg border border-[#D4D9E6] bg-[#FCFBFE] px-3 py-2 text-xs text-[#1E1934] placeholder:text-[#A39DBA] focus:border-[#6F5AC4] focus:bg-white focus:outline-none"
                      />
                      {savedNotice && (
                        <p className="text-[11px] text-[#524B6B]">
                          Saved inside this simulation. In the workspace,
                          assessments export as JSONL for future evaluation and
                          do not retrain the model immediately.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {mode === 'speaking-time' && (
              <div className="rounded-[18px] border border-[#D4D9E6]/90 bg-white/88 p-5 shadow-[0_18px_48px_rgba(30,25,52,0.05)] sm:p-6">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-semibold text-[#1E1934]">
                    <Clock className="h-4 w-4 text-[#604CB5]" aria-hidden="true" />
                    Participation &amp; speaking time
                  </span>
                  <span className="font-mono-data text-xs text-[#787192]">
                    Illustrative figures
                  </span>
                </div>

                <p className="mt-3 text-sm leading-relaxed text-[#524B6B]">
                  Speaking time is measured from finalized, timestamped words
                  received during recording (excluding silence and avoiding
                  double-counting overlaps).
                </p>

                <div className="mt-4">
                  <div className="flex h-4 w-full overflow-hidden rounded-full bg-[#EEE9F7]">
                    <div
                      className="h-full bg-[#6F5AC4]"
                      style={{ width: '58%' }}
                    />
                    <div
                      className="h-full bg-[#D87098]"
                      style={{ width: '42%' }}
                    />
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    {ILLUSTRATIVE_PARTICIPATION.map((p) => (
                      <div
                        key={p.speaker}
                        className="rounded-[11px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/75 p-3"
                      >
                        <div className="flex items-center gap-2 text-xs font-medium text-[#1E1934]">
                          <span
                            className="h-2.5 w-2.5 rounded-full"
                            style={{
                              backgroundColor:
                                p.speaker === 'A' ? '#6F5AC4' : '#D87098',
                            }}
                            aria-hidden="true"
                          />
                          {p.label}
                        </div>
                        <div className="font-mono-data mt-1 text-base font-medium text-[#1E1934]">
                          {p.duration} · {p.percentage}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <p className="mt-4 text-xs leading-relaxed text-[#787192]">
                  Values above are illustrative mockup figures, not calculated
                  from the 7 written turns. Imbalance notices appear only after
                  ≥30s measured speech, with both speakers active and one &gt;70%.
                </p>
              </div>
            )}

            {mode === 'argument-trail' && (
              <div className="rounded-[18px] border border-[#D4D9E6]/90 bg-white/88 p-5 shadow-[0_18px_48px_rgba(30,25,52,0.05)] sm:p-6">
                <div className="flex items-center gap-2 text-sm font-semibold text-[#1E1934]">
                  <GitBranch className="h-4 w-4 text-[#604CB5]" aria-hidden="true" />
                  Suggested argument trail
                </div>
                <p className="mt-3 text-sm leading-relaxed text-[#524B6B]">
                  The workspace combines local classifiers with linguistic safeguards.
                  Its suggested links need human review. This scripted example
                  illustrates the interaction. Click any link below to focus
                  the original turn and highlight its 3D node.
                </p>

                <div className="mt-4 space-y-2.5">
                  <button
                    type="button"
                    onClick={() => focusTurn(1)}
                    className="w-full rounded-[11px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/75 p-3 text-left transition-colors hover:border-[#6F5AC4]"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-[#5845A8]">Claim</span>
                      <span className="font-mono-data text-[#787192]">
                        Turn 01 · Speaker A
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[#383152]">
                      {SCRIPTED_TURNS[0].text}
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => focusTurn(2)}
                    className="w-full rounded-[11px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/75 p-3 text-left transition-colors hover:border-[#D87098]"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-[#B04B74]">
                        Rebuttal &amp; Reason / evidence
                      </span>
                      <span className="font-mono-data text-[#787192]">
                        Turn 02 · Speaker B
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[#383152]">
                      {SCRIPTED_TURNS[1].text}
                    </p>
                    <span className="font-mono-data mt-1.5 block text-[11px] text-[#787192]">
                      Tentative link: May challenge turn 01
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => focusTurn(3)}
                    className="w-full rounded-[11px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/75 p-3 text-left transition-colors hover:border-[#6F5AC4]"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-[#5845A8]">Question</span>
                      <span className="font-mono-data text-[#787192]">
                        Turn 03 · Speaker A
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[#383152]">
                      {SCRIPTED_TURNS[2].text}
                    </p>
                  </button>
                </div>
              </div>
            )}

            {mode === 'report' && (
              <div className="rounded-[18px] border border-[#D4D9E6]/90 bg-white/88 p-5 shadow-[0_18px_48px_rgba(30,25,52,0.05)] sm:p-6">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-semibold text-[#1E1934]">
                    <FileText className="h-4 w-4 text-[#604CB5]" aria-hidden="true" />
                    Extractive session report
                  </span>
                  <span className="font-mono-data text-xs text-[#787192]">
                    Source-linked
                  </span>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="rounded-[11px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/75 p-3">
                    <span className="text-xs font-medium text-[#787192]">
                      Main claims
                    </span>
                    <p className="mt-1 text-sm text-[#1E1934]">
                      “{SCRIPTED_TURNS[0].text}”
                    </p>
                    <button
                      type="button"
                      onClick={() => focusTurn(1)}
                      className="font-mono-data mt-1.5 text-xs font-medium text-[#604CB5] hover:underline"
                    >
                      Open Turn 01
                    </button>
                  </div>

                  <div className="rounded-[11px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/75 p-3">
                    <span className="text-xs font-medium text-[#787192]">
                      Expressed disagreement
                    </span>
                    <p className="mt-1 text-sm text-[#1E1934]">
                      “{SCRIPTED_TURNS[1].text}”
                    </p>
                    <button
                      type="button"
                      onClick={() => focusTurn(2)}
                      className="font-mono-data mt-1.5 text-xs font-medium text-[#B04B74] hover:underline"
                    >
                      Open Turn 02
                    </button>
                  </div>

                  <div className="rounded-[11px] border border-[#D87098]/40 bg-[#FDF4F8]/90 p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-[#787192]">
                        Questions to follow up
                      </span>
                      <span className="font-mono-data text-[11px] font-medium text-[#B04B74]">
                        No answer linked
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[#1E1934]">
                      “{SCRIPTED_TURNS[2].text}”
                    </p>
                    <button
                      type="button"
                      onClick={() => focusTurn(3)}
                      className="font-mono-data mt-1.5 text-xs font-medium text-[#604CB5] hover:underline"
                    >
                      Open Turn 03
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Persistent Transparency Reminder */}
            <div className="rounded-[11px] border border-[#D4D9E6]/85 bg-white/88 px-4 py-3 text-xs leading-relaxed text-[#524B6B]">
              Every observation above is a scripted illustration. In the live
              workspace, speaker attribution, drift detection, and argument roles
              remain assistive signals under human moderator control.
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
