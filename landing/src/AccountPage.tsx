import { useEffect, useState } from 'react';
import { ArrowLeft, GitBranch, MessageSquare, ShieldCheck } from 'lucide-react';
import { AuthForm } from './components/AuthForm';

export default function AccountPage() {
  const [mode,setMode] = useState<'login'|'register'>(window.location.pathname === '/signup' ? 'register' : 'login');
  useEffect(()=>{ document.title=`${mode === 'register' ? 'Create your account' : 'Sign in'} · Where’s your argument?`; },[mode]);
  function change(next: 'login'|'register') {
    setMode(next);
    window.history.replaceState(null,'',`${next === 'register' ? '/signup' : '/login'}${window.location.search}`);
  }
  return <main className="account-page">
    <section className="account-story">
      <a className="account-brand" href="/"><span className="pearl-mini"/>Where’s your argument?</a>
      <div className="account-story-copy"><span className="chip-lavender">Space for every voice</span><h2>Good conversations<br/>deserve a clear record.</h2><p>Follow the ideas. Notice what needs your attention. Return to the moments that matter.</p>
        <div className="account-preview" aria-label="Illustrative conversation preview"><span className="account-preview-label">A GLIMPSE OF YOUR WORKSPACE</span><div className="account-sample"><span>A</span><div><small>Claim · Speaker A</small><p>Public transport should be accessible to everyone.</p></div></div><div className="account-sample reply"><span>B</span><div><small>Response · Speaker B</small><p>How would we cover the cost?</p></div></div><div className="account-preview-link"><GitBranch size={13}/> An idea. A response. A source to return to.</div></div>
        <div className="account-story-features"><span><MessageSquare size={15}/> Follow both voices</span><span><ShieldCheck size={15}/> Keep the judgment yours</span></div>
      </div><p className="account-story-footer">English debates · Two voices · Human-led moderation</p>
    </section>
    <section className="account-entry"><a href="/" className="account-back"><ArrowLeft size={14}/> Back to the introduction</a><AuthForm key={mode} mode={mode} onModeChange={change}/><p className="account-entry-footer">Where’s your argument? · Moderator workspace</p></section>
  </main>;
}
