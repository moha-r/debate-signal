import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { AuthForm } from './AuthForm';

export function LoginModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [mode,setMode] = useState<'login'|'register'>('login');
  useEffect(() => {
    const element=dialog.current;
    if (open && !element?.open) element?.showModal();
    if (!open && element?.open) element.close();
  },[open]);
  return <dialog ref={dialog} className="account-dialog" aria-label="Workspace account access" onCancel={onClose} onClick={event=>{if(event.target===event.currentTarget) onClose();}}>
    <button type="button" className="account-close" aria-label="Close sign in" onClick={onClose}><X size={18}/></button>
    {open && <AuthForm key={mode} mode={mode} onModeChange={setMode}/>}
    <a className="account-full-page" href={mode==='login'?'/login':'/signup'}>Open the full account page</a>
  </dialog>;
}
