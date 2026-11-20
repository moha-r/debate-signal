import { useState, type ReactNode } from 'react';
import {
  ArrowRight,
  ChevronDown,
  Database,
  Download,
  FileEdit,
  GitBranch,
  GraduationCap,
  Layers,
  Mic,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { getWorkspaceUrl } from '../config';
import { CAPABILITY_COMPARISON, FAQ_ITEMS } from '../data/debateData';

function TiltFeatureCard({ children }: { children: ReactNode }) {
  const [tilt, setTilt] = useState({ rx: 0, ry: 0 });

  const handleMove = (e: React.MouseEvent<HTMLElement>) => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({ rx: -py * 4.5, ry: px * 4.5 });
  };

  return (
    <article
      onMouseMove={handleMove}
      onMouseLeave={() => setTilt({ rx: 0, ry: 0 })}
      style={{
        transform: `perspective(900px) rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg)`,
      }}
      className="group flex flex-col justify-between rounded-[16px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_16px_44px_rgba(30,25,52,0.05)] transition-[transform,border-color,box-shadow] duration-200 hover:border-[#6F5AC4]/45 hover:shadow-[0_20px_50px_rgba(111,90,196,0.12)]"
    >
      {children}
    </article>
  );
}

export function PostScrollSections({
  exampleSection,
}: {
  exampleSection?: ReactNode;
}) {
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);
  const workspaceUrl = getWorkspaceUrl('home');

  return (
    <div className="relative z-30 -mt-[24vh] rounded-t-[26px] border-t border-[#D4D9E6]/80 bg-transparent shadow-[0_-26px_60px_rgba(30,25,52,0.05)]">
      {/* ================================================================= */}
      {/* 1. PROBLEM & VALUE EDITORIAL BRIDGE + 3 JOURNEY FEATURE SCENES    */}
      {/* ================================================================= */}
      <section
        id="features"
        aria-labelledby="features-heading"
        className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8"
      >
        <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <span className="chip-lavender">Our workspace</span>
            <h2
              id="features-heading"
              className="mt-4 text-3xl font-medium leading-[1.02] tracking-[-0.03em] text-[#1E1934] sm:text-5xl"
              style={{ textWrap: 'balance' }}
            >
              Everything you need to follow a better debate.
            </h2>
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-[#524B6B] sm:text-base">
            From live transcription to structured argument review, bring every
            flagged moment and source turn into one calm workspace.
          </p>
        </div>

        {/* Three Tactile 3D-Tilting Showcase Cards */}
        <div className="mt-12 grid gap-5 lg:grid-cols-3">
          {/* Card 1 */}
          <TiltFeatureCard>
            <div className="flex items-center justify-between">
              <span className="font-mono-data text-[11px] uppercase tracking-[0.12em] text-[#787192]">
                [During the debate]
              </span>
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#F2EEFB] text-xs font-medium text-[#604CB5] transition-transform duration-300 group-hover:-rotate-45">
                →
              </span>
            </div>

            <div className="my-8 rounded-[12px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/78 p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 font-medium text-[#1E1934]">
                  <span className="h-2 w-2 rounded-full bg-[#6F5AC4]" aria-hidden="true" />
                  Speaker A · Turn 01
                </span>
                <span className="font-mono-data text-[11px] text-[#787192]">
                  00:14
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[#383152]">
                “School uniforms can reduce pressure to buy expensive clothes.”
              </p>
              <div className="mt-3 flex items-center gap-2 border-t border-[#D4D9E6]/70 pt-2.5 text-[11px] text-[#524B6B]">
                <Mic className="h-3.5 w-3.5 text-[#6F5AC4]" aria-hidden="true" />
                <span>Automatic A/B labels + manual correction</span>
              </div>
            </div>

            <div>
              <h3 className="text-2xl font-medium leading-[1.08] tracking-[-0.025em] text-[#1E1934]">
                Live transcription &amp; speaker labels
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-[#524B6B]">
                Follow two English speakers through a shared microphone with
                automatic attribution and contextual alerts for personal remarks
                and sustained drift.
              </p>
            </div>
          </TiltFeatureCard>

          {/* Card 2 */}
          <TiltFeatureCard>
            <div className="flex items-center justify-between">
              <span className="font-mono-data text-[11px] uppercase tracking-[0.12em] text-[#787192]">
                [See the structure]
              </span>
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#FDF4F8] text-xs font-medium text-[#D87098] transition-transform duration-300 group-hover:-rotate-45">
                →
              </span>
            </div>

            <div className="my-8 rounded-[12px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/78 p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-[#1E1934]">
                  Measured speaking time
                </span>
                <span className="font-mono-data text-[11px] text-[#787192]">
                  Word timestamps
                </span>
              </div>
              <div className="mt-3 flex h-2.5 w-full overflow-hidden rounded-full bg-[#E9E4F4]">
                <div className="h-full w-[58%] bg-[#6F5AC4]" />
                <div className="h-full w-[42%] bg-[#D87098]" />
              </div>
              <div className="mt-3 flex items-center gap-2 border-t border-[#D4D9E6]/70 pt-2.5 text-[11px] text-[#524B6B]">
                <GitBranch className="h-3.5 w-3.5 text-[#604CB5]" aria-hidden="true" />
                <span>Claims, reasons, rebuttals &amp; follow-ups</span>
              </div>
            </div>

            <div>
              <h3 className="text-2xl font-medium leading-[1.08] tracking-[-0.025em] text-[#1E1934]">
                Argument trail &amp; participation
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-[#524B6B]">
                Explore suggested claims, reasons, rebuttals, and questions
                alongside word-timestamp speaking time so both voices have room.
              </p>
            </div>
          </TiltFeatureCard>

          {/* Card 3 */}
          <TiltFeatureCard>
            <div className="flex items-center justify-between">
              <span className="font-mono-data text-[11px] uppercase tracking-[0.12em] text-[#787192]">
                [After the debate]
              </span>
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#F2EEFB] text-xs font-medium text-[#604CB5] transition-transform duration-300 group-hover:-rotate-45">
                →
              </span>
            </div>

            <div className="my-8 rounded-[12px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/78 p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-[#1E1934]">
                  Extractive report
                </span>
                <span className="font-mono-data text-[11px] text-[#787192]">
                  MD · JSON · JSONL
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[#383152]">
                Questions with no linked answer are flagged for human review
                alongside turn links.
              </p>
              <div className="mt-3 flex items-center gap-2 border-t border-[#D4D9E6]/70 pt-2.5 text-[11px] text-[#524B6B]">
                <Download className="h-3.5 w-3.5 text-[#604CB5]" aria-hidden="true" />
                <span>Local evaluation assessments exportable</span>
              </div>
            </div>

            <div>
              <h3 className="text-2xl font-medium leading-[1.08] tracking-[-0.025em] text-[#1E1934]">
                Reports, assessments &amp; exports
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-[#524B6B]">
                Leave with a source-linked extractive report in Markdown or JSON
                and save alert accuracy assessments locally as JSONL.
              </p>
            </div>
          </TiltFeatureCard>
        </div>

        {/* Compact Supporting Capabilities Strip */}
        <div className="mt-8 grid gap-3 rounded-[14px] border border-[#D4D9E6]/85 bg-white/88 p-4 shadow-[0_12px_36px_rgba(30,25,52,0.04)] sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex items-start gap-2.5">
            <Database className="mt-0.5 h-4 w-4 shrink-0 text-[#6F5AC4]" aria-hidden="true" />
            <div>
              <p className="text-xs font-medium text-[#1E1934]">
                Local SQLite storage
              </p>
              <p className="text-xs text-[#524B6B]">
                Sessions and assessments persist locally on your machine.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2.5">
            <Layers className="mt-0.5 h-4 w-4 shrink-0 text-[#604CB5]" aria-hidden="true" />
            <div>
              <p className="text-xs font-medium text-[#1E1934]">
                Prepared example mode
              </p>
              <p className="text-xs text-[#524B6B]">
                Explore the full workspace without recording audio.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2.5">
            <FileEdit className="mt-0.5 h-4 w-4 shrink-0 text-[#D87098]" aria-hidden="true" />
            <div>
              <p className="text-xs font-medium text-[#1E1934]">
                Typed turn entry
              </p>
              <p className="text-xs text-[#524B6B]">
                Add manual turns assigned to Speaker A or B anytime.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2.5">
            <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-[#604CB5]" aria-hidden="true" />
            <div>
              <p className="text-xs font-medium text-[#1E1934]">
                Draft word recovery
              </p>
              <p className="text-xs text-[#524B6B]">
                Recover draft words into the editor if audio drops.
              </p>
            </div>
          </div>
        </div>
      </section>

      {exampleSection}

      {/* ================================================================= */}
      {/* 2. HOW IT WORKS (3 STEPS)                                         */}
      {/* ================================================================= */}
      <section
        id="how-it-works"
        aria-labelledby="how-heading"
        className="border-t border-[#D4D9E6]/80 bg-transparent py-20 sm:py-24"
      >
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="max-w-xl">
            <p className="font-mono-data text-xs font-medium text-[#604CB5]">
              How it works
            </p>
            <h2
              id="how-heading"
              className="mt-2 text-3xl font-medium tracking-[-0.02em] text-[#1E1934] sm:text-4xl"
            >
              Three calm steps from question to review.
            </h2>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            <div className="rounded-[16px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_14px_38px_rgba(30,25,52,0.04)]">
              <span className="font-mono-data text-sm font-medium text-[#6F5AC4]">
                01
              </span>
              <h3 className="mt-3 text-lg font-medium text-[#1E1934]">
                Set the question
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[#524B6B]">
                Choose one clear discussion question as the reference anchor and
                prepare two speakers with optional display names.
              </p>
            </div>

            <div className="rounded-[16px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_14px_38px_rgba(30,25,52,0.04)]">
              <span className="font-mono-data text-sm font-medium text-[#D87098]">
                02
              </span>
              <h3 className="mt-3 text-lg font-medium text-[#1E1934]">
                Start the conversation
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[#524B6B]">
                Start recording inside the workspace and follow the running
                transcript, measured speaking time, and suggested alerts.
              </p>
            </div>

            <div className="rounded-[16px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_14px_38px_rgba(30,25,52,0.04)]">
              <span className="font-mono-data text-sm font-medium text-[#604CB5]">
                03
              </span>
              <h3 className="mt-3 text-lg font-medium text-[#1E1934]">
                Review with context
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[#524B6B]">
                Inspect surrounding turns behind any alert, explore the
                argument trail, record your assessments, and export the session.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ================================================================= */}
      {/* 3. SUGGESTED USE CASES + HONEST LIMITS                            */}
      {/* ================================================================= */}
      <section
        aria-labelledby="use-cases-heading"
        className="border-t border-[#D4D9E6]/80 bg-transparent py-20 sm:py-24"
      >
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <p className="font-mono-data text-xs font-medium text-[#604CB5]">
              Suggested use cases
            </p>
            <h2
              id="use-cases-heading"
              className="mt-2 text-3xl font-medium tracking-[-0.02em] text-[#1E1934] sm:text-4xl"
            >
              Designed for educational and moderated dialogues.
            </h2>
            <p className="mt-3 text-base text-[#524B6B]">
              These scenarios reflect intended workflows for this experimental
              academic project rather than formal institutional endorsements.
            </p>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            <div className="rounded-[16px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_14px_38px_rgba(30,25,52,0.04)]">
              <div className="flex h-10 w-10 items-center justify-center rounded-[11px] bg-[#F2EEFB] text-[#6F5AC4]">
                <GraduationCap className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-medium text-[#1E1934]">
                Classroom debates
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[#524B6B]">
                Teachers facilitating a structured discussion between two
                students can keep the core question visible and revisit
                specific turns afterward.
              </p>
            </div>

            <div className="rounded-[16px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_14px_38px_rgba(30,25,52,0.04)]">
              <div className="flex h-10 w-10 items-center justify-center rounded-[11px] bg-[#FDF4F8] text-[#D87098]">
                <Users className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-medium text-[#1E1934]">
                Debate club practice
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[#524B6B]">
                Debate trainees can compare measured speaking time, review
                unanswered follow-up questions, and export transcripts for
                coaching feedback.
              </p>
            </div>

            <div className="rounded-[16px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_14px_38px_rgba(30,25,52,0.04)]">
              <div className="flex h-10 w-10 items-center justify-center rounded-[11px] bg-[#F2EEFB] text-[#604CB5]">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-medium text-[#1E1934]">
                Moderated discussions
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[#524B6B]">
                A human moderator stays focused on listening while surfaced
                signals help spot personal remarks or sustained tangents early.
              </p>
            </div>
          </div>

          {/* Transparent Capabilities vs Current Version Limits */}
          <div className="mt-14 rounded-[18px] border border-[#D4D9E6]/85 bg-white/88 p-6 shadow-[0_16px_44px_rgba(30,25,52,0.05)] sm:p-8">
            <div className="max-w-2xl">
              <p className="font-mono-data text-xs font-medium text-[#604CB5]">
                Transparency &amp; scope
              </p>
              <h3 className="mt-1.5 text-2xl font-medium text-[#1E1934]">
                A clear picture of the current version
              </h3>
              <p className="mt-2 text-sm text-[#524B6B]">
                DebateSignal is an experimental academic prototype
                that runs locally. Here is what it provides today and what it
                intentionally does not claim.
              </p>
            </div>

            <div className="mt-6 grid gap-6 md:grid-cols-2">
              <div className="rounded-[12px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/78 p-5">
                <h4 className="text-sm font-semibold text-[#1E1934]">
                  Available in this version
                </h4>
                <ul className="mt-3 space-y-2 text-sm text-[#383152]">
                  {CAPABILITY_COMPARISON.availableNow.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#6F5AC4]"
                        aria-hidden="true"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-[12px] border border-[#D4D9E6]/80 bg-[#F3EFFB]/78 p-5">
                <h4 className="text-sm font-semibold text-[#1E1934]">
                  Not presented as an existing feature
                </h4>
                <ul className="mt-3 space-y-2 text-sm text-[#524B6B]">
                  {CAPABILITY_COMPARISON.notClaimed.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#C4CADA]"
                        aria-hidden="true"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ================================================================= */}
      {/* 4. FAQ ACCORDION                                                  */}
      {/* ================================================================= */}
      <section
        id="faq"
        aria-labelledby="faq-heading"
        className="border-t border-[#D4D9E6]/80 bg-transparent py-20 sm:py-24"
      >
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <p className="font-mono-data text-xs font-medium text-[#604CB5]">
              Frequently asked questions
            </p>
            <h2
              id="faq-heading"
              className="mt-2 text-3xl font-medium tracking-[-0.02em] text-[#1E1934] sm:text-4xl"
            >
              Clear answers about how it works
            </h2>
          </div>

          <div className="mt-10 divide-y divide-[#D4D9E6]/70 rounded-[16px] border border-[#D4D9E6]/90 bg-white/90 shadow-[0_16px_44px_rgba(30,25,52,0.05)]">
            {FAQ_ITEMS.map((item, idx) => {
              const isOpen = openFaqIndex === idx;
              return (
                <div key={item.question} className="px-5 sm:px-6">
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setOpenFaqIndex(isOpen ? null : idx)}
                    className="flex min-h-[56px] w-full items-center justify-between gap-4 py-4 text-left text-base font-medium text-[#1E1934] transition-colors hover:text-[#604CB5]"
                  >
                    <span>{item.question}</span>
                    <ChevronDown
                      className={`h-4 w-4 shrink-0 text-[#787192] transition-transform duration-200 ${
                        isOpen ? 'rotate-180 text-[#604CB5]' : ''
                      }`}
                      aria-hidden="true"
                    />
                  </button>
                  {isOpen && (
                    <div className="pb-5 text-sm leading-relaxed text-[#524B6B]">
                      {item.answer}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ================================================================= */}
      {/* 5. FINAL CTA & QUIET TRANSPARENT FOOTER                           */}
      {/* ================================================================= */}
      <section className="border-t border-[#D4D9E6]/80 bg-transparent py-20 sm:py-24">
        <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
          <div className="mx-auto mb-5 flex h-10 w-10 items-center justify-center rounded-full border border-[#D4D9E6] bg-white shadow-sm">
            <span className="pearl-mini h-5 w-5 rounded-full" aria-hidden="true" />
          </div>
          <h2
            className="text-3xl font-medium tracking-[-0.02em] text-[#1E1934] sm:text-4xl"
            style={{ textWrap: 'balance' }}
          >
            Give your next debate a clearer record.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-base leading-relaxed text-[#524B6B]">
            Bring two perspectives, set one question and leave with a
            conversation you can revisit.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <a
              href={workspaceUrl}
              className="btn-primary inline-flex min-h-[44px] items-center gap-2 whitespace-nowrap rounded-[11px] px-6 py-2.5 text-sm font-medium"
            >
              <span>Open workspace</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </a>
            <a
              href="#example"
              className="btn-secondary inline-flex min-h-[44px] items-center whitespace-nowrap rounded-[11px] px-5 py-2.5 text-sm font-medium"
            >
              Back to scripted example
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-[#D4D9E6]/80 bg-[#FCFBFE]/92 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-4 sm:flex-row sm:items-center sm:px-6 lg:px-8">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[#1E1934]">
              <span className="pearl-mini h-4 w-4 rounded-full ring-1 ring-[#D4D9E6]" aria-hidden="true" />
              <span>DebateSignal</span>
            </div>
            <p className="mt-1 text-xs text-[#787192]">
              Experimental academic project running locally · Human-led debate
              moderation workspace.
            </p>
          </div>

          <nav
            aria-label="Footer navigation"
            className="flex flex-wrap items-center gap-5 text-xs font-medium text-[#524B6B]"
          >
            <a href="#features" className="hover:text-[#604CB5]">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-[#604CB5]">
              How it works
            </a>
            <a href="#example" className="hover:text-[#604CB5]">
              Scripted example
            </a>
            <a href="#faq" className="hover:text-[#604CB5]">
              FAQ
            </a>
            <a href={workspaceUrl} className="font-semibold text-[#604CB5] hover:text-[#5845A8]">
              Open workspace
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
