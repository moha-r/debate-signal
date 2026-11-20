import {createRoot} from 'react-dom/client';
import { lazy, Suspense } from 'react';
import './index.css';
import AccountPage from './AccountPage';

const Landing = lazy(() => import('./App.tsx'));
createRoot(document.getElementById('root')!).render(['/login','/signup'].includes(window.location.pathname) ? <AccountPage/> : <Suspense fallback={<div role="status" style={{padding:32,color:'#8f6ac5'}}>Opening the conversation…</div>}><Landing /></Suspense>);
