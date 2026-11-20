import { useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, Eye, EyeOff, LoaderCircle, LockKeyhole, Mail, UserRound } from 'lucide-react';
import { accountRequest, workspaceDestination, type AccountStatus } from '../auth';

interface Props { mode: 'login' | 'register'; onModeChange: (mode: 'login' | 'register') => void }

export function AuthForm({ mode, onModeChange }: Props) {
  const register = mode === 'register';
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [firstAccount, setFirstAccount] = useState(false);
  useEffect(() => {
    let cancelled = false;
    accountRequest<AccountStatus>('me').then(data => {
      if (cancelled) return;
      if (data.user) { window.location.replace(workspaceDestination()); return; }
      setFirstAccount(data.setup_required);
    }).catch(() => { if (!cancelled) setError('The account service is unavailable. Please try again.'); });
    return () => { cancelled = true; };
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError(''); setBusy(true);
    try {
      await accountRequest(register ? 'register' : 'login', { name: name.trim(), email: email.trim(), password, remember });
      setPassword('');
      try { localStorage.setItem('debate-account-change', crypto.randomUUID()); } catch { /* Account cookies still work when storage is disabled. */ }
      window.location.assign(workspaceDestination());
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Could not sign in. Try again.');
      setBusy(false);
    }
  }
  return <div className="account-form">
    <span className="chip-lavender">{register ? 'Your personal workspace' : 'Welcome back'}</span>
    <h1>{register ? 'A space for your next conversation.' : 'Pick up the conversation.'}</h1>
    <p className="account-intro">{register ? 'Create an account to save your debates, reviews and the ideas worth returning to.' : 'Sign in to your saved debates, argument trails and moderator reviews.'}</p>
    {firstAccount && <div className="account-first">This is the first account on this installation. Your existing local debates will belong to the first account you create. <button type="button" disabled={busy} onClick={() => onModeChange('register')}>Create your account <ArrowRight size={12}/></button></div>}
    <form onSubmit={submit}>
      {error && <p role="alert" className="account-error">{error}</p>}
      {register && <label htmlFor="account-name">Your name<div className="account-input"><UserRound size={17}/><input id="account-name" autoComplete="name" value={name} onChange={e => setName(e.target.value)} maxLength={80} placeholder="How should we address you?" required disabled={busy}/></div></label>}
      <label htmlFor="account-email">Email address<div className="account-input"><Mail size={17}/><input id="account-email" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} maxLength={254} placeholder="you@example.com" required disabled={busy}/></div></label>
      <label htmlFor="account-password">Password<div className="account-input"><LockKeyhole size={17}/><input id="account-password" type={visible ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 8 : 1} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} placeholder={register ? 'At least 8 characters' : 'Enter your password'} required disabled={busy}/><button type="button" aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible} onClick={() => setVisible(v=>!v)}>{visible ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div>{register && <small>Use at least 8 characters. A longer passphrase works well.</small>}</label>
      <label className="account-remember"><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)} disabled={busy}/> Keep me signed in on this device</label>
      <button className="btn-primary account-submit" type="submit" disabled={busy}>{busy ? <><LoaderCircle size={17} className="account-spin"/>{register ? 'Creating your workspace…' : 'Signing you in…'}</> : <>{register ? 'Create account' : 'Sign in'}<ArrowRight size={17}/></>}</button>
    </form>
    <p className="account-switch">{register ? 'Already have an account?' : 'New to the conversation?'} <button type="button" disabled={busy} onClick={() => onModeChange(register ? 'login' : 'register')}>{register ? 'Sign in' : 'Create an account'}</button></p>
    <p className="account-footnote"><LockKeyhole size={12}/> Your debates are saved to your account on this installation.</p>
  </div>;
}
