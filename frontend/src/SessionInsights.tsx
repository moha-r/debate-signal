import { useState } from 'react';
import { ArrowDownToLine, ArrowUpRight, Check, Clock3, GitBranch, MessageCircleQuestion, ShieldCheck } from 'lucide-react';
import type { ArgumentCorrection, ArgumentNode, ModeratorAlert, Session, Speaker, TurnSpeaker } from './types';

type NameFor = (side: TurnSpeaker) => string;
export const speechTime = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
const roles: Record<ArgumentNode['role'], string> = {
  claim: 'Claim', reason: 'Reason / evidence', rebuttal: 'Rebuttal', question: 'Question', agreement: 'Agreement', unclassified: 'Other contribution',
};
const responseLabels: Record<string,string> = { possible_answer: 'Potential answer', confirmed_answer: 'Moderator-confirmed answer', partial_answer: 'Partial response', uncertain_answer: 'Uncertain response', insufficient_evidence: 'Evidence not supplied', declined: 'Declined to answer' };

export function Participation({ session, nameFor }: { session: Session; nameFor: NameFor }) {
  const data = session.insights?.participation;
  const measured = Boolean(data?.timed_turns);
  return <section className="surface participation-panel" aria-label="Speaking time">
    <div className="small-heading"><h2><Clock3 size={15}/> Space for both voices</h2><span className="insight-eyebrow">SPEAKING TIME</span></div>
    {measured && data ? <>
      <div className="participation-labels">{(['A', 'B'] as Speaker[]).map((side) => <div key={side}><span className={`voice-dot side-${side}`}/><strong>{nameFor(side)}</strong><span>{speechTime(data.seconds[side])}</span><small>{Math.round((data.shares[side] || 0)*100)}%</small></div>)}</div>
      <div className="participation-track" aria-label="Measured speech proportions">{(['A','B','Unknown'] as TurnSpeaker[]).map((side) => <span key={side} className={`side-${side}`} style={{ width: `${(data.shares[side] || 0)*100}%` }}/>)}</div>
      {data.dominant_speaker && <p className="balance-advisory" role="status">{nameFor(data.dominant_speaker)} has most of the measured speaking time. Consider inviting the other voice in.</p>}
      <p className="insight-note">Word timing from audio · pauses excluded{data.seconds.Unknown > 0 ? ` · ${speechTime(data.seconds.Unknown)} unconfirmed` : ''}{data.untimed_turns ? ` · ${data.untimed_turns} turns without timing` : ''}</p>
      <details className="measurement-details"><summary>How participation is measured</summary><p>{data.measurement} Balance suggestions begin after {data.policy.minimum_speech_seconds}s of measured speech, with both voices present and one voice above {Math.round(data.policy.dominance_share*100)}%.</p></details>
    </> : <div className="participation-empty"><AudioMark/><div><strong>Speaking time starts with your next recording.</strong><p>Typed turns and older recordings have no audio timing.</p></div></div>}
  </section>;
}
function AudioMark() { return <span className="timing-mark" aria-hidden="true">{[10,20,30,17,25,12,21].map((h,i) => <i key={i} style={{height:h}}/>)}</span>; }

export function ArgumentMap({ session, nameFor, onSource, compact = false, busy = false, onCorrect }: { session: Session; nameFor: NameFor; onSource: (turn: number) => void; compact?: boolean; busy?: boolean; onCorrect?: (turn: number, correction: ArgumentCorrection) => void }) {
  const [filter, setFilter] = useState('all');
  const nodes = session.insights?.arguments || [];
  const visible = nodes.filter((n) => filter === 'all' ? n.role !== 'unclassified' : (n.roles || [n.role]).includes(filter));
  const shown = compact ? visible.slice(-3) : visible;
  return <section className={`surface argument-panel ${compact ? 'compact' : ''}`}>
    <div className="small-heading"><h2><GitBranch size={16}/> {compact ? 'Argument trail' : 'How the argument connects'}</h2><span className="tag lavender">{visible.length} contributions</span></div>
    <p className="section-description">Follow claims, reasons and responses back to the conversation.</p>
    {!compact && <div className="argument-filters" aria-label="Filter argument roles">{[['all','All'],['claim','Claims'],['reason','Reasons / evidence'],['rebuttal','Rebuttals'],['question','Questions'],['agreement','Agreements'],['unclassified','Other']].map(([value,label]) => <button key={value} aria-pressed={filter === value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}<span>{value === 'all' ? nodes.filter(n=>n.role !== 'unclassified').length : nodes.filter(n=>(n.roles || [n.role]).includes(value)).length}</span></button>)}</div>}
    {shown.length ? <ol className="argument-trail">{shown.map((node) => <li key={node.turn} className={`argument-node role-${node.role}`}>
      <span className="argument-pin" aria-hidden="true"/><div className="argument-node-heading"><span className="role-label">{roles[node.role]}{node.role !== 'reason' && node.roles?.includes('reason') ? ' · Reason / evidence' : ''}</span><span>{nameFor(node.speaker)}</span><button className="source-link" onClick={() => onSource(node.turn)}>Turn {node.turn}<ArrowUpRight size={12}/></button></div>
      <p>{node.text}</p>
      {node.link && <button className="argument-connection" onClick={() => onSource(node.link!.turn)}><GitBranch size={12}/>{node.link.tentative ? 'Suggested: ' : 'Moderator: '}{node.link.relation === 'answers' ? 'responds to' : node.link.relation === 'attack' ? 'challenges' : node.link.relation === 'support' ? 'supports' : 'relates to'} turn {node.link.turn}<ArrowUpRight size={11}/></button>}
      {node.evidence_requested && <span className="evidence-request"><MessageCircleQuestion size={12}/> Evidence requested</span>}
      {!compact && <><small className="argument-cue">{node.cue}{node.role_confidence != null ? ` · Model score ${Math.round(node.role_confidence*100)}% (uncalibrated)` : ''}{node.annotation_source === 'moderator' ? ' · Moderator reviewed' : ''}{!node.link && ['claim','reason','rebuttal','agreement'].includes(node.role) ? ' · No reliable target selected' : ''}</small>{onCorrect && <ArgumentReview key={`${node.turn}-${session.revision}`} node={node} nodes={nodes} busy={busy} onSave={(correction)=>onCorrect(node.turn,correction)}/>}</>}
    </li>)}</ol> : <div className="calm-empty"><GitBranch size={26}/><strong>{nodes.length ? 'No contributions in this view.' : 'The first idea starts the trail.'}</strong><p>{nodes.length ? 'Try another role filter.' : 'Start a conversation to see its arguments take shape.'}</p></div>}
    <p className="insight-note">Suggested roles and links · evidence references are unverified.</p>
  </section>;
}

function ArgumentReview({ node, nodes, busy, onSave }: { node: ArgumentNode; nodes: ArgumentNode[]; busy: boolean; onSave: (correction: ArgumentCorrection) => void }) {
  const [role,setRole]=useState(node.role);
  const [target,setTarget]=useState(node.link ? String(node.link.turn) : '');
  const [relation,setRelation]=useState<'support'|'attack'|'answers'>(node.link?.relation || 'support');
  const [reason,setReason]=useState(node.review?.reason || '');
  const substantive=!['question','unclassified'].includes(role);
  const eligible=nodes.filter(n=>n.turn<node.turn && (relation==='answers' ? n.role==='question' : ['claim','reason','rebuttal','agreement'].includes(n.role)));
  const selected=eligible.some(n=>String(n.turn)===target) ? target : '';
  return <details className="argument-review"><summary>Review role & connection{node.annotation_source==='moderator' ? ' · Saved' : ''}</summary>
    <form onSubmit={event=>{event.preventDefault();onSave({role,target:substantive && selected ? Number(selected) : null,relation:substantive && selected ? relation : null,reason});}}>
      <label>Primary role<select value={role} disabled={busy} onChange={e=>setRole(e.target.value as ArgumentNode['role'])}>{Object.entries(roles).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      {substantive && <><label>Relationship<select value={relation} disabled={busy} onChange={e=>{setRelation(e.target.value as typeof relation);setTarget('');}}><option value="support">Supports an argument</option><option value="attack">Challenges an argument</option><option value="answers">Answers a question</option></select></label><label>Earlier source<select value={selected} disabled={busy} onChange={e=>setTarget(e.target.value)}><option value="">No connection</option>{eligible.map(n=><option key={n.turn} value={n.turn}>Turn {n.turn} · {n.text.slice(0,65)}</option>)}</select></label></>}
      <label>Review note (optional)<textarea rows={2} maxLength={1000} value={reason} disabled={busy} onChange={e=>setReason(e.target.value)}/></label>
      <p className="insight-note">The original prediction stays in the session export. This saves your annotation; it does not retrain the model.</p>
      <button className="btn secondary small" disabled={busy}>Save review<Check size={12}/></button>
    </form>
  </details>;
}

export function AlertFeedback({ alert, busy, onSave }: { alert: ModeratorAlert; busy: boolean; onSave: (verdict: 'correct' | 'incorrect', reason: string) => void }) {
  const [verdict, setVerdict] = useState<'correct' | 'incorrect' | ''>(alert.feedback?.verdict || '');
  const [reason, setReason] = useState(alert.feedback?.reason || '');
  return <form className="feedback-panel" onSubmit={(event) => { event.preventDefault(); if (verdict) onSave(verdict,reason); }}>
    <div className="small-heading"><h3><ShieldCheck size={14}/> Was this alert accurate?</h3>{alert.feedback && <span className="feedback-saved"><Check size={12}/> Saved</span>}</div>
    <p>Your assessment is saved with the original turn for future model evaluation.</p>
    <div className="feedback-options">{(['correct','incorrect'] as const).map((value) => <button type="button" key={value} disabled={busy} aria-pressed={verdict === value} className={verdict === value ? 'chosen' : ''} onClick={() => setVerdict(value)}>{value === 'correct' ? 'Alert is correct' : 'Alert is incorrect'}</button>)}</div>
    <label>Reason <span>optional</span><textarea value={reason} disabled={busy} maxLength={1000} rows={2} placeholder="What did the model miss?" onChange={(event) => setReason(event.target.value)}/></label>
    <button className="btn secondary small" disabled={busy || !verdict}>{alert.feedback ? 'Update assessment' : 'Save assessment'}<Check size={13}/></button>
  </form>;
}

export function SessionReport({ session, nameFor, onSource }: { session: Session; nameFor: NameFor; onSource: (turn: number) => void }) {
  const report = session.insights?.report;
  const turnsById = new Map(session.turns.map(t => [t.number,t]));
  const feedbackCount = session.alerts.filter(a => a.feedback).length;
  function download() {
    if (!report) return;
    const lines = [`# ${session.topic}`, '', `Session ${session.id}`, `Started ${session.started_at}`, '',
      ...(['claims','reasons','agreements','disagreements'] as const).flatMap(key => [`## ${key[0].toUpperCase()+key.slice(1)}`, ...report![key].map(id=> { const t=turnsById.get(id)!; return `- [Turn ${id}](#turn-${id}) ${nameFor(t.speaker)}: ${t.text}`; }), '']),
      '## Questions', ...report.questions.map(q=>`- [Turn ${q.turn}](#turn-${q.turn}) ${q.text} (${q.responses?.length ? q.responses.map(r=>`${responseLabels[r.status] || r.status}: [Turn ${r.turn}](#turn-${r.turn})`).join('; ') : q.answer_turns.length ? `Possible answers: ${q.answer_turns.map(id=>`[Turn ${id}](#turn-${id})`).join(', ')}` : 'No answer linked'})`), '',
      '## Argument annotations', ...(session.insights?.arguments || []).map(n=>`- Turn ${n.turn}: ${roles[n.role]}${n.link ? `; ${n.link.relation || 'relates to'} turn ${n.link.turn} (${n.link.tentative ? 'suggested' : 'moderator reviewed'})` : '; no connection selected'}${n.annotation_source==='moderator' ? `; moderator note: ${n.review?.reason || '(none)'}` : ''}`), '',
      '## Participation', ...(session.insights?.participation.timed_turns ? [...(['A','B','Unknown'] as TurnSpeaker[]).map(s=>`${nameFor(s)}: ${session.insights!.participation.seconds[s]} measured seconds`), session.insights.participation.measurement, `${session.insights.participation.untimed_turns} turns have no audio timing.`] : ['No audio timing is available. Typed turns and older recordings are untimed.']),
      '', `Moderator assessments saved: ${feedbackCount}`, '', report.limitations, '', '## Full transcript',
      ...session.turns.flatMap(t=>[`### Turn ${t.number}`,`${nameFor(t.speaker)}: ${t.text}`,''])];
    const url = URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/markdown;charset=utf-8'}));
    const a = document.createElement('a'); a.href=url; a.download=`debate-report-${session.started_at.slice(0,10)}.md`; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  if (!report) return <div className="surface calm-empty"><p>No report is available for this session.</p></div>;
  return <div className="session-report">
    <section className="report-cover surface"><div><span className="insight-eyebrow">A CONVERSATION, IN PERSPECTIVE</span><h2>Your session, with every source attached.</h2><p>{session.turns.length} speaking turns · {feedbackCount} moderator assessments · {session.alerts.filter(a=>a.status==='Pending').length} alerts awaiting review</p></div><button className="btn primary small" onClick={download}><ArrowDownToLine size={14}/> Download report</button></section>
    <Participation session={session} nameFor={nameFor}/>
    <div className="report-grid">{([['claims','Main claims'],['reasons','Reasons & evidence references'],['agreements','Expressed agreement'],['disagreements','Expressed disagreement']] as const).map(([key,title]) => <section className={`surface report-section report-${key}`} key={key}>
      <div className="small-heading"><h2>{title}</h2><span className="tiny-count">{report[key].length}</span></div>
      {report[key].length ? <ul>{report[key].map(id=> { const turn=turnsById.get(id)!; return <li key={id}><button className="source-link" onClick={()=>onSource(id)}>{nameFor(turn.speaker)} · Turn {id}<ArrowUpRight size={12}/></button><p>{turn.text}</p></li>; })}</ul> : <p className="report-empty">No explicit contributions identified here.</p>}
    </section>)}</div>
    <section className="surface report-section"><div className="small-heading"><h2><MessageCircleQuestion size={16}/> Questions to follow up</h2><span className="tiny-count">{report.questions.filter(q=>q.status ? q.status!=='moderator_answered' : !q.answer_turns.length).length} awaiting follow-up / review</span></div>
      {report.questions.length ? <ul className="report-questions">{report.questions.map(q=><li key={q.turn}><button className="source-link" onClick={()=>onSource(q.turn)}>Turn {q.turn}<ArrowUpRight size={12}/></button><p>{q.text}</p><div className="question-state">{q.evidence_requested && <span className="tag lavender">Evidence requested</span>}{q.responses?.length ? q.responses.map(r=><button className="text-link" key={r.turn} onClick={()=>onSource(r.turn)}>{responseLabels[r.status] || r.status} · turn {r.turn}{r.answer_span && <span className="answer-span">“{r.answer_span.text}”</span>}<ArrowUpRight size={12}/></button>) : q.answer_turns.length ? q.answer_turns.map(id=><button className="text-link" key={id} onClick={()=>onSource(id)}>Possible answer · turn {id}<ArrowUpRight size={12}/></button>) : <span>No answer linked · review the transcript</span>}</div></li>)}</ul> : <p className="report-empty">No questions identified in this session.</p>}
    </section>{feedbackCount > 0 && <a className="btn secondary small feedback-export" href={`/api/sessions/${session.id}/feedback`}><ArrowDownToLine size={14}/> Export {feedbackCount} moderator assessments</a>}<p className="report-method">{report.limitations} Assessments are saved for later training and do not retrain the model immediately.</p>
  </div>;
}
