import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, ArrowDown, ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, AudioLines, Check,
  CheckCheck, ChevronDown, ChevronRight, CircleAlert, CircleHelp, Clock3, FileText, Flag,
  FolderOpen, Home, Layers3, LoaderCircle, MessageSquare, Mic, MoreHorizontal, Plus, Search,
  Settings2, ShieldCheck, Sparkles, UsersRound, X, LogOut,
} from 'lucide-react';
import '@fontsource-variable/dm-sans';
import '@fontsource/ibm-plex-mono/400.css';
import VoiceConsole from './VoiceConsole';
import Presence from './Presence';
import MicrophoneCheck from './MicrophoneCheck';
import { AlertFeedback, ArgumentMap, Participation, SessionReport, speechTime } from './SessionInsights';
import type { ArgumentCorrection, ModeratorAlert, Session, Speaker, Turn, TurnSpeaker } from './types';
import './styles.css';

type Page = 'home' | 'library' | 'new' | 'room' | 'review';
type Names = Record<Speaker, string>;
interface Entry { id: string; names: Names; demo: boolean; ended: boolean }
const defaultNames = { A: 'Speaker A', B: 'Speaker B' };
const topics = [
  'Should schools require students to wear uniforms?',
  'Should AI tools be allowed in university assignments?',
  'Should cities make public transport free?',
];
const pageNames: Record<Page, string> = {
  home: 'Overview', library: 'My debates', new: 'New debate', room: 'Live room', review: 'Review queue',
};
function route(): Page {
  const hash = location.hash.slice(1);
  return ['home', 'library', 'new', 'room', 'review'].includes(hash) ? hash as Page : 'home';
}
async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  }).catch(() => { throw new Error('The local service is unavailable. Check the server and try again.'); });
  if (!response.ok) {
    if (response.status === 401) window.location.replace(`/login?next=${encodeURIComponent('/app/'+location.hash)}`);
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed. Try again.');
  }
  return response.json();
}
function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
function topicLabel(topic: Turn['topic']) {
  if (topic.reason === 'conversation_management') return 'Neutral';
  if (topic.state === 'on_topic') return 'On topic';
  return topic.state === 'off_topic' ? 'Off topic' : 'Unclear';
}
function turnTime(start: string, value: string) {
  const seconds = Math.max(0, Math.floor((Date.parse(value) - Date.parse(start)) / 1000));
  return [Math.floor(seconds / 60), seconds % 60].map((number) => String(number).padStart(2, '0')).join(':');
}
function Avatar({ side, name, large = false }: { side: TurnSpeaker; name?: string; large?: boolean }) {
  return <span className={`avatar avatar-${side.toLowerCase()} ${large ? 'large' : ''}`} aria-hidden="true">
    {side === 'Unknown' ? '?' : !name || /^Speaker [AB]$/.test(name) ? side : name.trim().slice(0, 1).toUpperCase()}
  </span>;
}

function App() {
  const [user,setUser] = useState<{id:string;name:string;email:string}|null>(null);
  const [page, setPage] = useState<Page>(route);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [entries, setEntries] = useState<Record<string, Entry>>({});
  const [active, setActive] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [topic, setTopic] = useState(topics[0]);
  const [names, setNames] = useState<Names>(defaultNames);
  const [step, setStep] = useState(0);
  const [deviceId, setDeviceId] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<number | null>(null);
  const [following, setFollowing] = useState(true);
  const [reviewFilter, setReviewFilter] = useState<'Pending' | 'All'>('Pending');
  const [reviewTab, setReviewTab] = useState<'moments' | 'transcript' | 'arguments' | 'report'>('moments');
  const [draft, setDraft] = useState('');
  const [draftSide, setDraftSide] = useState<Speaker>('A');
  const [writing, setWriting] = useState(false);
  const [help, setHelp] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const list = useRef<HTMLDivElement>(null);
  const cardRefs = useRef(new Map<number, HTMLButtonElement>());
  const operation = useRef(false);
  const workspace = useRef({ sessions, entries, active, voiceBusy });
  workspace.current = { sessions, entries, active, voiceBusy };

  const session = sessions.find((item) => item.id === active);
  const entry = entries[active];
  const participantNames = entry?.names || defaultNames;
  const nameFor = (side: TurnSpeaker) => side === 'Unknown' ? 'Unconfirmed speaker' : participantNames[side];
  const turns = session?.turns || [];
  const allAlerts = sessions.flatMap((item) => item.alerts.map((alert) => ({ ...alert, sessionId: item.id, topic: item.topic })));
  const pending = session?.alerts.filter((alert) => alert.status === 'Pending') || [];
  const pendingAll = allAlerts.filter((alert) => alert.status === 'Pending');
  const selectedTurn = turns.find((turn) => turn.number === selected);
  const selectedAlert = session?.alerts.find((alert) => alert.turn === selected &&
    (reviewFilter === 'All' || alert.status === 'Pending'));
  const reviewAlerts = (session?.alerts || []).filter((alert) => reviewFilter === 'All' || alert.status === 'Pending');
  const visibleTurns = turns.filter((turn) => turn.text.toLowerCase().includes(search.toLowerCase().trim()));
  const recent = [...sessions].sort((a, b) => b.started_at.localeCompare(a.started_at));
  const wordCount = turns.reduce((sum, turn) => sum + turn.text.split(/\s+/).filter(Boolean).length, 0);

  useEffect(() => {
    let cancelled = false;
    api<{user:{id:string;name:string;email:string}|null}>('/api/auth/me').then(({user})=> {
      if (cancelled) return;
      if (user) setUser(user);
      else window.location.replace(`/login?next=${encodeURIComponent('/app/'+location.hash)}`);
    }).catch(()=>undefined);
    let stored: { entries?: Entry[]; active?: string } = {};
    try { stored = JSON.parse(sessionStorage.getItem('argument-workspace') || '{}'); } catch { /* Start with an empty workspace. */ }
    const records = Array.isArray(stored.entries) ? stored.entries.filter((item) =>
      item && typeof item.id === 'string' && /^[a-f0-9-]{36}$/.test(item.id)) : [];
    if (!records.length) {
      try {
        const legacy = sessionStorage.getItem('debate-session');
        if (legacy && /^[a-f0-9-]{36}$/.test(legacy)) records.push({ id: legacy, names: defaultNames, demo: false, ended: false });
      } catch { /* Browser storage is optional. */ }
    }
    api<Session[]>('/api/sessions')
      .then((saved) => {
        if (cancelled) return;
        const found = saved.map(state => ({ state, item: records.find(item=>item.id === state.id) || {
          id: state.id, names: state.participants || defaultNames, demo: Boolean(state.example), ended: false,
        } }));
        setSessions(found.map(({ state }) => state));
        setEntries(Object.fromEntries(found.map(({ item }) => [item.id, {
          ...item, names: { A: String(item.names?.A || 'Speaker A'), B: String(item.names?.B || 'Speaker B') },
        }])));
        const restoredId = found.some(({ state }) => state.id === stored.active) ? stored.active! : found[0]?.state.id || '';
        setActive(restoredId);
        const restored = found.find(({ state }) => state.id === restoredId)?.state;
        setSelected(restored?.alerts.find((alert) => alert.status === 'Pending')?.turn || restored?.turns.at(-1)?.number || null);
        setLoading(false);
      }).catch((error) => { if (!cancelled) { setLoading(false); setError(error instanceof Error ? error.message : 'Could not load your saved debates.'); } });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (loading) return;
    try { sessionStorage.setItem('argument-workspace', JSON.stringify({ entries: Object.values(entries), active })); }
    catch { /* The workspace also remains available in the current page. */ }
  }, [entries, active, loading]);

  useEffect(() => {
    function changed(event: StorageEvent) {
      if (event.key !== 'debate-account-change') return;
      setSessions([]); setEntries({}); setActive('');
      window.location.replace('/app/');
    }
    addEventListener('storage',changed);
    return () => removeEventListener('storage',changed);
  }, []);

  useEffect(() => {
    function change() {
      if (workspace.current.voiceBusy && route() !== 'room') { location.replace('#room'); return; }
      setPage(route());
      setSearch('');
      setSidebarOpen(false);
      setHelp(false);
    }
    addEventListener('hashchange', change);
    return () => removeEventListener('hashchange', change);
  }, []);

  useEffect(() => {
    if (following && !search && list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [turns.length, following, search, page]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 3600);
    return () => clearTimeout(timer);
  }, [toast]);

  function navigate(target: Page) {
    if (voiceBusy && target !== 'room') return;
    setSearch('');
    setHelp(false);
    setPage(target);
    setSidebarOpen(false);
    location.hash = target;
  }
  function newDebate(initialTopic?: string) {
    if (voiceBusy) return;
    setTopic(initialTopic || topics[0]);
    setNames(defaultNames);
    setStep(0);
    navigate('new');
  }
  function update(state: Session) {
    setSessions((current) => {
      const previous = current.find((item) => item.id === state.id);
      return previous && previous.revision > state.revision ? current
        : previous ? current.map((item) => item.id === state.id ? state : item) : [...current, state];
    });
  }
  async function perform(action: () => Promise<void>) {
    if (operation.current) return;
    operation.current = true;
    setBusy(true);
    setError('');
    try { await action(); }
    catch (error) {
      const id = workspace.current.active;
      if (id) await api<Session>(`/api/sessions/${id}`).then(update).catch(() => undefined);
      setError(error instanceof Error ? error.message : 'Please try again.');
    } finally { operation.current = false; setBusy(false); }
  }
  function create(demo = false) {
    if (voiceBusy) return;
    void perform(async () => {
      const state = await api<Session>('/api/sessions', 'POST', { topic, example: demo, participants: demo ? defaultNames : names });
      const item: Entry = { id: state.id, names: demo ? defaultNames : {
        A: names.A.trim() || 'Speaker A', B: names.B.trim() || 'Speaker B',
      }, demo, ended: false };
      setEntries((current) => ({ ...current, [state.id]: item }));
      update(state);
      setActive(state.id);
      setSelected(state.turns.at(-1)?.number || null);
      setFollowing(true);
      setDraft('');
      setWriting(false);
      setReviewFilter('Pending');
      setReviewTab('moments');
      navigate('room');
      if (demo) setToast('Example session loaded. Its transcript and alerts are ready to explore.');
    });
  }
  function open(id: string, destination: Page, turn?: number) {
    setActive(id);
    const state = sessions.find((item) => item.id === id);
    setSelected(turn || state?.alerts.find((alert) => alert.status === 'Pending')?.turn || state?.turns.at(-1)?.number || null);
    setReviewFilter('Pending');
    if (destination === 'review') setReviewTab('moments');
    setFollowing(true);
    navigate(destination);
  }
  function inspect(number: number) {
    setFollowing(false);
    setSelected(number);
  }
  function locate(number: number) {
    setSearch('');
    inspect(number);
    requestAnimationFrame(() => {
      const card = cardRefs.current.get(number);
      if (!card || !list.current) return;
      list.current.scrollTo({ top: list.current.scrollTop + card.getBoundingClientRect().top - list.current.getBoundingClientRect().top - 14,
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      card.focus({ preventScroll: true });
    });
  }
  function review(alert: ModeratorAlert, decision: 'Reviewed' | 'Dismissed') {
    void perform(async () => {
      const state = workspace.current.sessions.find((item) => item.id === active);
      if (!state) return;
      const updated = await api<Session>(`/api/sessions/${active}/alerts/${alert.id}`, 'PATCH', { decision, revision: state.revision });
      update(updated);
      setToast(`Alert ${decision.toLowerCase()}.`);
      if (page === 'review' && reviewFilter === 'Pending') setSelected(updated.alerts.find((item) => item.status === 'Pending')?.turn || alert.turn);
    });
  }
  function correct(number: number, side: Speaker) {
    void perform(async () => {
      update(await api<Session>(`/api/sessions/${active}/turns/${number}/speaker`, 'PATCH', { speaker: side }));
      setToast('Speaker updated in the transcript and linked alerts.');
    });
  }
  function correctArgument(number: number, correction: ArgumentCorrection) {
    void perform(async () => {
      const state=workspace.current.sessions.find(item=>item.id===active);
      if (!state) return;
      update(await api<Session>(`/api/sessions/${active}/turns/${number}/argument`,'PATCH',{...correction,revision:state.revision}));
      setToast('Argument review saved. Original prediction preserved in the session export.');
    });
  }
  function assess(alert: ModeratorAlert, verdict: 'correct' | 'incorrect', reason: string) {
    void perform(async () => {
      const state = workspace.current.sessions.find((item) => item.id === active);
      if (!state) return;
      update(await api<Session>(`/api/sessions/${active}/alerts/${alert.id}/feedback`, 'PATCH', { verdict, reason, revision: state.revision }));
      setToast('Assessment saved for future evaluation.');
    });
  }
  function sourceTurn(number: number) {
    setFollowing(false);
    setReviewTab('transcript');
    setSelected(number);
    setSearch('');
    setPage('review');
    location.hash = 'review';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      cardRefs.current.get(number)?.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      cardRefs.current.get(number)?.focus({ preventScroll: true });
    }));
  }
  function addTurn() {
    if (!session || !draft.trim()) return;
    void perform(async () => {
      const updated = await api<Session>(`/api/sessions/${active}/turns`, 'POST', { speaker: draftSide, text: draft, revision: session.revision });
      update(updated);
      setDraft('');
      setFollowing(true);
      setSelected(updated.turns.at(-1)?.number || null);
    });
  }
  function signOut() {
    if (voiceBusy) return;
    void perform(async () => {
      await api('/api/auth/logout','POST',{});
      try { localStorage.setItem('debate-account-change',crypto.randomUUID()); } catch { /* No credentials are stored here. */ }
      try { sessionStorage.removeItem('argument-workspace'); sessionStorage.removeItem('debate-session'); } catch { /* Storage can be disabled. */ }
      setSessions([]); setEntries({}); setActive('');
      window.location.assign('/login');
    });
  }
  function finish() {
    const id = workspace.current.active;
    setEntries((current) => current[id] ? { ...current, [id]: { ...current[id], ended: true } } : current);
    const state = workspace.current.sessions.find((item) => item.id === id);
    setSelected(state?.alerts.find((alert) => alert.status === 'Pending')?.turn || state?.turns.at(-1)?.number || null);
    setReviewTab('report');
    setReviewFilter('Pending');
    workspace.current.voiceBusy = false;
    setVoiceBusy(false);
    setPage('review');
    location.hash = 'review';
  }
  function exportSession() {
    if (!session) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify({ ...session, participants: participantNames }, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `debate-${session.started_at.slice(0, 10)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function sessionCard(state: Session) {
    const item = entries[state.id];
    const count = state.alerts.filter((alert) => alert.status === 'Pending').length;
    return <button className="session-card" key={state.id} onClick={() => open(state.id, item?.ended ? 'review' : 'room')}>
      <div className={`session-cover cover-${sessions.indexOf(state) % 3}`}><span className="cover-voices"><Avatar side="A" large/><i/><Avatar side="B" large/></span>
        <span className="cover-play"><ArrowUpRight size={18}/></span><span className="cover-kind">{item?.demo ? 'Example debate' : item?.ended ? 'Completed' : 'Ready to continue'}</span></div>
      <div className="session-card-body"><h3>{state.topic}</h3><p>{dateLabel(state.started_at)}<span>·</span>{state.turns.length} turns</p>
        <div><span className={`tag ${count ? 'amber' : 'neutral'}`}>{count ? `${count} to review` : 'Up to date'}</span><span className="card-link">{item?.ended ? 'Review session' : 'Open room'}<ArrowUpRight size={12}/></span></div>
      </div>
    </button>;
  }
  function transcript(reviewing = false) {
    return <section className={`transcript-card surface ${reviewing ? 'review-transcript' : ''}`} aria-label="Conversation transcript">
      <div className="small-heading"><h2><FileText size={16}/> Transcript <span className="tiny-count">{turns.length}</span></h2>
        <button type="button" className="btn ghost mini" onClick={() => { setFollowing(true); setSearch(''); setSelected(turns.at(-1)?.number || null); }} disabled={!turns.length}><ArrowDown size={12}/>{following ? 'Following latest' : 'Jump to latest'}</button></div>
      <label className="inline-search"><Search size={14}/><input type="search" placeholder="Find a word or phrase" aria-label="Search transcript" value={search}
        onChange={(event) => { setSearch(event.target.value); setFollowing(false); }}/></label>
      <div className="transcript-scroll" ref={list} onWheel={(event) => { if (event.deltaY < 0) setFollowing(false); }}
        onTouchMove={() => setFollowing(false)} tabIndex={0} aria-label="Transcript turns">
        {!turns.length ? <div className="empty-state"><span className="empty-symbol"><MessageSquare size={25}/></span><h3>Your conversation lives here.</h3><p>Start recording above. Completed thoughts will appear with their detected speaker.</p></div>
          : !visibleTurns.length ? <div className="empty-state"><Search size={25}/><h3>No matching turns</h3><button className="btn ghost" onClick={() => setSearch('')}>Clear search</button></div>
          : <ol>{visibleTurns.map((turn) => <li key={turn.number}>
            <button className={`transcript-turn ${selected === turn.number ? 'selected' : ''}`} type="button" onClick={() => inspect(turn.number)}
              aria-pressed={selected === turn.number} ref={(element) => { if (element) cardRefs.current.set(turn.number, element); else cardRefs.current.delete(turn.number); }}>
              <Avatar side={turn.speaker} name={nameFor(turn.speaker)}/><span className="turn-copy"><span className="turn-byline"><strong>{nameFor(turn.speaker)}</strong>
                <time>{session && turnTime(session.started_at, turn.time)}</time>{turn.source === 'voice' && <Mic size={11}/>}</span><span className="turn-words">{turn.text}</span>
                {(turn.personal_attack || turn.topic.alert) && <span className="turn-markers">{turn.personal_attack && <span><Flag size={10}/> Possible attack</span>}{turn.topic.alert && <span><Activity size={10}/> Topic drift</span>}</span>}
              </span><span className="turn-index">{String(turn.number).padStart(2, '0')}</span>
            </button>
          </li>)}</ol>}
      </div>
      {!reviewing && <details className="typed-turn" open={writing} onToggle={(event) => setWriting(event.currentTarget.open)}>
        <summary><Plus size={13}/> Add a typed turn <ChevronDown size={13}/></summary><form onSubmit={(event) => { event.preventDefault(); addTurn(); }}>
          <div className="typed-speakers">{(['A','B'] as Speaker[]).map((side) => <button type="button" key={side} aria-pressed={draftSide === side} disabled={voiceBusy || busy} onClick={() => setDraftSide(side)}>{participantNames[side]}</button>)}</div>
          <label className="sr-only" htmlFor="draft-turn">Typed turn</label><textarea id="draft-turn" value={draft} maxLength={4000} rows={2} onChange={(event) => setDraft(event.target.value)} disabled={voiceBusy || busy} placeholder="Write a completed thought…"/>
          <button className="btn primary small" disabled={!draft.trim() || voiceBusy || busy}>Analyze turn<ArrowRight size={13}/></button>
        </form>
      </details>}
    </section>;
  }

  return <div className="workspace-shell">
    {sidebarOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}/>}
    <aside className={`app-sidebar ${sidebarOpen ? 'mobile-open' : ''}`}>
      <button className="sidebar-close btn icon" aria-label="Close navigation menu" onClick={() => setSidebarOpen(false)}><X size={15}/></button>
      <a className="wordmark" href="#home" onClick={(event) => { event.preventDefault(); navigate('home'); }} aria-label="Where’s your argument? Home"><span className="brand-gem"><Sparkles size={18}/></span><span>Where’s your<br/><strong>argument?</strong></span></a>
      <button className="btn primary sidebar-create" disabled={voiceBusy || busy || loading} onClick={() => newDebate()}><Plus size={16}/> New debate</button>
      <span className="nav-label">WORKSPACE</span>
      <nav aria-label="Main navigation">
        {([{page:'home', label:'Overview', icon:Home}, {page:'library',label:'My debates',icon:FolderOpen}, {page:'review',label:'Review queue',icon:ShieldCheck}] as const).map((item) =>
          <button key={item.page} className={page === item.page ? 'active' : ''} disabled={voiceBusy} aria-current={page === item.page ? 'page' : undefined} onClick={() => {
            if (item.page === 'review' && (pendingAll[0]?.sessionId || active)) open(pendingAll[0]?.sessionId || active, 'review');
            else navigate(item.page);
          }}>
            <item.icon size={16}/>{item.label}{item.page === 'review' && pendingAll.length > 0 && <b>{pendingAll.length}</b>}
          </button>)}
        {session && <button className={page === 'room' ? 'active' : ''} onClick={() => navigate('room')} aria-current={page === 'room' ? 'page' : undefined}><AudioLines size={16}/> Live room{voiceBusy && <i className="status-dot recording"/>}</button>}
      </nav>
      <div className="sidebar-recent"><span className="nav-label">RECENT SESSIONS</span>{recent.slice(0,4).map((item) => <button disabled={voiceBusy} key={item.id} onClick={() => open(item.id, entries[item.id]?.ended ? 'review' : 'room')}><MessageSquare size={13}/><span>{item.topic}</span></button>)}
        {!sessions.length && <p>Your debates will appear here.</p>}</div>
      <div className="sidebar-bottom"><button disabled={voiceBusy} onClick={() => { setHelp((value) => !value); setSidebarOpen(false); }}><CircleHelp size={16}/> How it works</button>
        <button disabled={voiceBusy || busy} onClick={signOut}><LogOut size={15}/> Sign out</button>
        <div className="workspace-profile"><span>{user?.name.slice(0,1).toUpperCase() || 'M'}</span><div><strong>{user?.name || 'Moderator workspace'}</strong><small>{user?.email || 'Personal account'}</small></div><ShieldCheck size={15}/></div></div>
    </aside>
    <div className="workspace-main">
      <header className="app-header"><button className="mobile-nav btn icon" aria-label="Toggle navigation" onClick={() => setSidebarOpen((value) => !value)}><Layers3 size={18}/></button>
        <span className="workspace-switch"><Sparkles size={13}/> Personal workspace</span><span className="header-crumb"><ChevronRight size={12}/>{pageNames[page]}</span>
        <div className="header-right"><span className="local-indicator"><i className={voiceBusy ? 'recording' : ''}/>{voiceBusy ? 'Recording in progress' : 'English debates'}</span>
          {page !== 'new' && <button className="btn primary small" disabled={voiceBusy || busy || loading} onClick={() => newDebate()}><Plus size={14}/> New debate</button>}
        </div>
      </header>
      <main className={`page-content page-${page}`}>
        {error && <div className="notice-banner" role="alert"><CircleAlert size={16}/><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error"><X size={15}/></button></div>}
        {loading && <div className="loading-workspace"><LoaderCircle size={20} className="spin"/> Opening your workspace…</div>}

        {!loading && page === 'home' && <>
          <section className="welcome"><Presence/><h1>Space for <em>every voice.</em><br/>Ready for your next debate?</h1><p>Bring two perspectives together. Keep the conversation on track.</p></section>
          <div className="overview-grid"><div className="overview-primary">
            <section className="start-card surface"><div className="small-heading"><h2>Start a conversation</h2><span className="subtle">English · Two speakers</span></div>
              <div className="start-modes"><button className="selected" onClick={() => newDebate()}><Mic size={16}/> Live debate</button><button onClick={() => create(true)} disabled={busy}><Sparkles size={16}/> Explore an example</button></div>
              <div className="quick-topic"><MessageSquare size={15}/><label className="sr-only" htmlFor="quick-topic">Debate topic</label><input id="quick-topic" value={topic} maxLength={300} onChange={(event) => setTopic(event.target.value)} placeholder="What would you like to discuss?"/><button className="btn primary" onClick={() => newDebate(topic)}>Set up debate <ArrowUpRight size={14}/></button></div>
              <div className="topic-ideas"><span>Try a topic</span>{topics.slice(0,2).map((idea,index) => <button key={idea} onClick={() => setTopic(idea)}>{index === 0 ? 'School uniforms' : 'AI in education'}<ArrowUpRight size={10}/></button>)}</div>
            </section>
            <section className="recent-section"><div className="section-title"><h2>Recent debates</h2><button className="text-link" onClick={() => navigate('library')}>View all <ArrowRight size={13}/></button></div>
              {recent.length ? <div className="session-grid">{recent.slice(0,4).map(sessionCard)}</div> : <div className="empty-library surface"><span className="empty-stack"><FileText size={23}/></span><h3>Your first debate starts a collection.</h3><p>Completed and in-progress sessions will appear here.</p><button className="text-link" onClick={() => create(true)} disabled={busy}>See how a session works <ArrowUpRight size={13}/></button></div>}
            </section>
          </div><aside className="overview-aside">
            <section className="surface glance-card"><h2>Your workspace</h2><div><span><MessageSquare size={15}/> Debates</span><strong>{sessions.length}</strong></div><div><span><AudioLines size={15}/> Speaking turns</span><strong>{sessions.reduce((sum,item) => sum + item.turns.length,0)}</strong></div><div><span><ShieldCheck size={15}/> Waiting for review</span><strong>{pendingAll.length}</strong></div></section>
            <section className="surface attention-card"><div className="small-heading"><h2>Needs your attention</h2><span className="tiny-count">{pendingAll.length}</span></div>
              {pendingAll.length ? pendingAll.slice(0,4).map((alert) => <button className="attention-item" key={alert.sessionId+alert.id} onClick={() => open(alert.sessionId,'review',alert.turn)}><span className={`attention-icon ${alert.kind === 'Topic drift' ? 'amber' : 'rose'}`}>{alert.kind === 'Topic drift' ? <Activity size={14}/> : <Flag size={14}/>}</span><span><strong>{alert.kind}</strong><small>{alert.topic}</small></span><ChevronRight size={13}/></button>)
                : <div className="calm-empty"><CheckCheck size={24}/><strong>All clear for now.</strong><p>Moments that need a human eye will appear here.</p></div>}
            </section>
            <div className="human-note"><span><ShieldCheck size={18}/></span><div><strong>You’re in the moderator’s seat.</strong><p>The system suggests moments to review. Every decision stays with you.</p></div></div>
          </aside></div>
        </>}

        {!loading && page === 'library' && <>
          <div className="page-heading"><div><span className="overline">YOUR WORKSPACE</span><h1>My debates</h1><p>A place for every conversation you’ve started.</p></div><span className="tag neutral">{sessions.length} sessions</span></div>
          <label className="library-search"><Search size={16}/><input type="search" aria-label="Search debates" placeholder="Search your debates" value={search} onChange={(event) => setSearch(event.target.value)}/></label>
          {recent.length ? <div className="library-grid">{recent.filter((item) => item.topic.toLowerCase().includes(search.toLowerCase())).map(sessionCard)}</div>
            : <div className="empty-state surface"><FolderOpen size={30}/><h3>A fresh workspace.</h3><p>Create your first debate to get started.</p><button className="btn primary" onClick={() => newDebate()}>Create a debate <Plus size={14}/></button></div>}
          {recent.length > 0 && !recent.some((item) => item.topic.toLowerCase().includes(search.toLowerCase())) && <div className="empty-state"><Search size={24}/><h3>No debates match your search.</h3><button className="text-link" onClick={() => setSearch('')}>Clear search</button></div>}
          <p className="storage-note"><ShieldCheck size={13}/> Sessions are available in this browser tab while the local service is running. Export a session to keep a copy.</p>
        </>}

        {!loading && page === 'new' && <div className="setup-layout">
          <div className="setup-intro"><span className="overline">A LITTLE PREPARATION</span><h1>A better debate<br/>starts here.</h1><p>Give the conversation a direction.<br/>We’ll help you follow where it goes.</p>
            <ol className="setup-steps">{['Set the topic','Meet the voices','Check your sound'].map((label,index) => <li key={label} className={step === index ? 'current' : step > index ? 'complete' : ''}><span>{step > index ? <Check size={13}/> : index + 1}</span><div><strong>{label}</strong><small>{['One clear question','Two distinct perspectives','One shared microphone'][index]}</small></div></li>)}</ol>
            <div className="setup-note"><ShieldCheck size={17}/><p>Personal attacks and topic drift are flagged for your review during the conversation.</p></div>
          </div>
          <section className="setup-card surface" key={step}>
            <span className="step-indicator">STEP {step + 1} OF 3</span>
            {step === 0 && <><span className="setup-symbol"><MessageSquare size={23}/></span><h2>What’s on the table?</h2><p>Frame the debate as a question with two possible viewpoints.</p>
              <label className="form-label" htmlFor="setup-topic">Discussion question<textarea id="setup-topic" value={topic} rows={4} maxLength={300} onChange={(event) => setTopic(event.target.value)} placeholder="Should…?"/></label>
              <div className="suggestions"><span>Need a starting point?</span>{topics.map((idea) => <button key={idea} onClick={() => setTopic(idea)}>{idea}<ArrowUpRight size={13}/></button>)}</div>
            </>}
            {step === 1 && <><span className="setup-symbol"><UsersRound size={24}/></span><h2>Two voices, detected automatically.</h2><p>Start the microphone once and take turns speaking. The system assigns each completed turn to its detected voice.</p>
              <div className="detected-speakers">{(['A','B'] as Speaker[]).map((side) => <div key={side}><Avatar side={side} large/><strong>Speaker {side}</strong><span>Detected during recording</span></div>)}</div>
              <details className="optional-names"><summary>Add display names <span>Optional</span><ChevronDown size={13}/></summary>
                {(['A','B'] as Speaker[]).map((side,index) => <label className="participant-input" key={side}><Avatar side={side} large/><span><strong>{index === 0 ? 'First detected voice · Speaker A' : 'Second detected voice · Speaker B'}</strong><input maxLength={40} value={names[side]} onChange={(event) => setNames((current) => ({ ...current,[side]: event.target.value }))} aria-label={`Speaker ${side} name`}/></span></label>)}
              </details>
              <div className="soft-info"><AudioLines size={16}/><p>Speaker labels follow the voice in each recording. Brief or unclear speech can remain unconfirmed for review.</p></div>
            </>}
            {step === 2 && <><MicrophoneCheck deviceId={deviceId} onDevice={setDeviceId}/><div className="setup-recap"><span>YOUR DISCUSSION</span><strong>{topic}</strong><small>{names.A || 'Speaker A'}<i/>{names.B || 'Speaker B'}<i/>English</small></div></>}
            <div className="setup-footer"><button className="btn ghost" onClick={() => step ? setStep(step - 1) : navigate('home')} disabled={busy}><ArrowLeft size={14}/>{step ? 'Back' : 'Cancel'}</button>
              <button className="btn primary" disabled={busy || (step === 0 && topic.trim().split(/\s+/).length < 3)} onClick={() => step < 2 ? setStep(step + 1) : create()}>
                {busy ? <LoaderCircle className="spin" size={14}/> : null}{step < 2 ? 'Continue' : 'Open live room'}<ArrowRight size={14}/>
              </button></div>
          </section>
        </div>}

        {!loading && (page === 'room' || page === 'review') && !session && <div className="empty-state surface"><MessageSquare size={28}/><h1>A conversation is waiting to happen.</h1><p>Open a debate from your workspace or create a new one.</p><button className="btn primary" onClick={() => newDebate()}>Create a debate <Plus size={14}/></button></div>}

        {!loading && session && (page === 'room' || page === 'review') && <div className="session-page-heading"><div><button className="back-link" disabled={voiceBusy} onClick={() => navigate('library')}><ArrowLeft size={12}/> My debates</button><h1>{session.topic}</h1><p>{dateLabel(session.started_at)}<span>·</span>English<span>·</span>{entry?.demo ? 'Example session' : 'Two participants'}</p></div><div className="session-header-actions">
          <button className="btn secondary small" onClick={exportSession}><ArrowDownToLine size={14}/> Export</button>
          {page === 'room' ? <button className="btn secondary small" disabled={voiceBusy} onClick={() => open(active,'review')}>Review session<ArrowUpRight size={13}/></button>
            : <button className="btn primary small" onClick={() => navigate('room')}><Mic size={13}/> Open live room</button>}
        </div></div>}

        <div hidden={page !== 'room' || !session || loading} className="room-recording">
          <VoiceConsole sessionId={session?.id} blocked={busy || loading} names={participantNames} initialDeviceId={deviceId}
            onBusy={setVoiceBusy} onStart={() => newDebate()} onFinish={finish}
            onRecover={(text) => { setDraft((current) => (current ? current+'\n'+text : text).slice(0,4000)); setWriting(true); setToast('Recovered words are available in the typed draft.'); }}
            onUpdate={(state) => { update(state); if (following) setSelected(state.turns.at(-1)?.number || null); }}/>
        </div>

        {!loading && session && page === 'room' && <>
          <div className="room-participants">{(['A','B'] as Speaker[]).map((side) => {
            const count = turns.filter((turn) => turn.speaker === side).length;
            const timing = session.insights?.participation;
            return <section className={`speaker-card speaker-${side.toLowerCase()}`} key={side}><Avatar side={side} name={participantNames[side]} large/><div><h2>{participantNames[side]}</h2><p>Speaker {side}<span>·</span>{count} {count === 1 ? 'turn' : 'turns'}</p></div><div className="speaker-share"><strong>{timing?.timed_turns ? speechTime(timing.seconds[side]) : '—'}</strong><span>{timing?.timed_turns ? 'speech time' : 'no audio timing'}</span></div></section>;
          })}</div>
          <Participation session={session} nameFor={nameFor}/>
          <div className="room-grid">{transcript()}<aside className="room-assist">
            <section className="surface assist-card"><div className="small-heading"><h2><ShieldCheck size={16}/> Moderator assist</h2><span className="tiny-count">{pending.length}</span></div>
              <p className="section-description">Moments worth a closer look.</p>{pending.length ? pending.map((alert) => <article className="live-alert" key={alert.id}>
                <button className="live-alert-content" onClick={() => locate(alert.turn)}><span className={`alert-kind ${alert.kind === 'Topic drift' ? 'amber' : 'rose'}`}>{alert.kind === 'Topic drift' ? <Activity size={12}/> : <Flag size={12}/>} {alert.kind}</span><p>“{alert.text}”</p><small>{nameFor(alert.speaker)}<span>·</span>Turn {alert.turn}<ArrowUpRight size={12}/></small></button>
                <div className="decision-actions"><button disabled={busy} onClick={() => review(alert,'Dismissed')}><X size={12}/> Dismiss</button><button disabled={busy} onClick={() => review(alert,'Reviewed')}><Check size={12}/> Reviewed</button></div>
              </article>) : <div className="calm-empty"><ShieldCheck size={27}/><strong>Room to keep talking.</strong><p>Alerts will appear here when a moment needs your attention.</p></div>}
            </section>
            {selectedTurn && <section className="surface turn-detail-mini"><div className="small-heading"><h3>Selected turn</h3><span className="subtle">#{selectedTurn.number}</span></div>
              {selectedTurn.source === 'voice' && <div className="automatic-attribution"><span><AudioLines size={13}/> Detected speaker</span><strong>{nameFor(selectedTurn.speaker)}</strong>
                <button type="button" className="text-link" disabled={voiceBusy} onClick={() => open(active,'review',selectedTurn.number)}>Review speaker label <ArrowUpRight size={12}/></button>
              </div>}
              <div className="mini-score"><span>Personal attack score</span><strong>{Math.round(selectedTurn.attack_probability*100)}%</strong></div>
              <div className="mini-score"><span>Topic relevance</span><strong>{topicLabel(selectedTurn.topic)}</strong></div>
            </section>}
            <ArgumentMap key={session.id} session={session} nameFor={nameFor} onSource={locate} compact/>
            <button className="btn secondary small" disabled={voiceBusy} onClick={() => { setReviewTab('arguments'); navigate('review'); }}>Explore argument map <ArrowUpRight size={13}/></button>
            <p className="assist-disclosure"><ShieldCheck size={12}/> Suggestions support your judgment. Topic relevance is experimental.</p>
          </aside></div>
        </>}

        {!loading && session && page === 'review' && <>
          <div className="review-summary"><div><span className="summary-icon lavender"><AudioLines size={19}/></span><span><strong>{turns.length}</strong><small>Speaking turns</small></span></div><div><span className="summary-icon peach"><Flag size={18}/></span><span><strong>{pending.length}</strong><small>Awaiting review</small></span></div><div><span className="summary-icon mint"><CheckCheck size={19}/></span><span><strong>{session.alerts.filter((alert) => alert.status !== 'Pending').length}</strong><small>Reviewed or dismissed</small></span></div><div><span className="summary-icon neutral"><FileText size={18}/></span><span><strong>{wordCount}</strong><small>Transcript words</small></span></div></div>
          <div className="review-tabs" role="group" aria-label="Review view"><button aria-pressed={reviewTab === 'moments'} className={reviewTab === 'moments' ? 'active' : ''} onClick={() => setReviewTab('moments')}><ShieldCheck size={14}/> Moments to review</button><button aria-pressed={reviewTab === 'transcript'} className={reviewTab === 'transcript' ? 'active' : ''} onClick={() => setReviewTab('transcript')}><FileText size={14}/> Full transcript</button><button aria-pressed={reviewTab === 'arguments'} className={reviewTab === 'arguments' ? 'active' : ''} onClick={() => setReviewTab('arguments')}><Layers3 size={14}/> Argument map</button><button aria-pressed={reviewTab === 'report'} className={reviewTab === 'report' ? 'active' : ''} onClick={() => setReviewTab('report')}><ArrowDownToLine size={14}/> Session report</button></div>
          {reviewTab === 'arguments' ? <ArgumentMap key={session.id} session={session} nameFor={nameFor} onSource={sourceTurn} busy={busy || voiceBusy} onCorrect={correctArgument}/> : reviewTab === 'report' ? <SessionReport session={session} nameFor={nameFor} onSource={sourceTurn}/> : reviewTab === 'transcript' ? transcript(true) : <div className="review-layout">
            <section className="surface moments-list"><div className="small-heading"><h2>Flagged moments</h2><select value={reviewFilter} aria-label="Filter moments" onChange={(event) => setReviewFilter(event.target.value as 'All'|'Pending')}><option>Pending</option><option>All</option></select></div>
              {reviewAlerts.length ? reviewAlerts.map((alert) => <button key={alert.id} className={`moment-item ${selected === alert.turn ? 'selected' : ''}`} onClick={() => setSelected(alert.turn)}>
                <span className={`attention-icon ${alert.kind === 'Topic drift' ? 'amber' : 'rose'}`}>{alert.kind === 'Topic drift' ? <Activity size={15}/> : <Flag size={15}/>}</span><span><strong>{alert.kind}</strong><p>{alert.text}</p><small>{nameFor(alert.speaker)}<span>·</span>Turn {alert.turn}</small></span><ChevronRight size={14}/>
              </button>) : <div className="calm-empty"><CheckCheck size={28}/><strong>{session.alerts.length ? 'You’re all caught up.' : 'No flagged moments.'}</strong><p>{session.alerts.length ? 'Choose All to revisit your decisions.' : 'Open the transcript to explore this session.'}</p></div>}
            </section>
            <section className="surface moment-detail">
              {selectedTurn ? <><div className="small-heading"><span className={`tag ${selectedAlert?.kind === 'Personal attack' ? 'rose' : 'lavender'}`}>{selectedAlert?.kind || 'Speaking turn'}</span><span className="subtle">{selectedAlert?.status || `Turn ${selectedTurn.number}`}</span></div>
                <div className="quote-author"><Avatar side={selectedTurn.speaker} name={nameFor(selectedTurn.speaker)}/><strong>{nameFor(selectedTurn.speaker)}</strong><time>{turnTime(session.started_at,selectedTurn.time)}</time></div>
                <blockquote>{selectedTurn.text}</blockquote>
                {selectedAlert?.status === 'Pending' && <div className="review-decisions"><button className="btn secondary" disabled={busy} onClick={() => review(selectedAlert,'Dismissed')}><X size={14}/> Dismiss alert</button><button className="btn primary" disabled={busy} onClick={() => review(selectedAlert,'Reviewed')}><Check size={14}/> Mark reviewed</button></div>}
                {selectedAlert && <AlertFeedback key={`${session.id}-${selectedAlert.id}-${selectedAlert.feedback?.time || ''}`} alert={selectedAlert} busy={busy} onSave={(verdict,reason)=>assess(selectedAlert,verdict,reason)}/>}
                {selectedTurn.source === 'voice' && <details className="optional-correction"><summary><Settings2 size={13}/> Correct speaker label <span>Optional</span><ChevronDown size={13}/></summary>
                  <p>Use this if the detected voice was assigned to the wrong participant.</p>
                  <label className="speaker-correction">Assign this recorded turn to<select aria-label="Correct speaker" value={selectedTurn.speaker} disabled={busy} onChange={(event) => correct(selectedTurn.number,event.target.value as Speaker)}>
                    {selectedTurn.speaker === 'Unknown' && <option value="Unknown" disabled>Unconfirmed</option>}<option value="A">{participantNames.A}</option><option value="B">{participantNames.B}</option></select></label>
                </details>}
                <div className="evidence-scores"><div><span>Personal attack score</span><strong>{Math.round(selectedTurn.attack_probability*100)}%</strong><meter min={0} max={1} value={selectedTurn.attack_probability}/>{selectedTurn.attack_context?.suppressed && <small>{selectedTurn.attack_context.reason}</small>}</div><div><span>Topic relevance</span><strong>{topicLabel(selectedTurn.topic)}</strong><small>{selectedTurn.topic.reason === 'conversation_management' ? 'Manages the conversation without counting toward topic drift' : selectedTurn.topic.used_context ? 'Recent topical context used' : 'Direct topic comparison'}</small></div></div>
                <details className="context-detail" open><summary>Conversation context <ChevronDown size={13}/></summary>{turns.filter((turn) => turn.number >= selectedTurn.number-4 && turn.number <= selectedTurn.number+1).map((turn) => <div className={turn.number === selectedTurn.number ? 'focused-context' : ''} key={turn.number}><strong>{nameFor(turn.speaker)} · Turn {turn.number}</strong><p>{turn.text}</p></div>)}</details>
                <p className="detail-disclaimer">These scores are model outputs. Use the surrounding conversation to make your decision.</p>
              </> : <div className="empty-state"><ShieldCheck size={28}/><h3>Every moment has context.</h3><p>Select a flagged moment to inspect the conversation around it.</p></div>}
            </section>
          </div>}
        </>}
      </main>
    </div>
    {toast && <div className="toast" role="status"><Check size={14}/>{toast}</div>}
    {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><section className="help-dialog surface" role="dialog" aria-modal="true" aria-labelledby="help-title" onClick={(event) => event.stopPropagation()}><div className="small-heading"><h2 id="help-title">A thoughtful debate, in a few steps.</h2><button className="btn icon" aria-label="Close guide" onClick={() => setHelp(false)}><X size={16}/></button></div>
      <ol><li><strong>Set the topic.</strong><p>Choose one clear question and name the two voices.</p></li><li><strong>Share the microphone.</strong><p>Speak in turns. Speaker labels are detected automatically during each recording.</p></li><li><strong>Stay in the conversation.</strong><p>Read the transcript and review possible personal attacks or sustained topic drift.</p></li><li><strong>Look back with context.</strong><p>End recording to review moments, correct speaker labels and export the transcript.</p></li></ol><p className="storage-note">Your debates and moderator assessments are saved locally on this computer. Microphone audio streams to AssemblyAI during recording.</p><button className="btn primary" onClick={() => setHelp(false)}>Got it <Check size={14}/></button>
    </section></div>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
