export interface Account { id: string; name: string; email: string; created_at: string }
export interface AccountStatus { user: Account | null; setup_required: boolean }

export function workspaceDestination() {
  const next = new URLSearchParams(window.location.search).get('next');
  if (next && next.startsWith('/app/') && !next.includes('\\')) {
    const target = new URL(next, window.location.origin);
    if (target.origin === window.location.origin && target.pathname.startsWith('/app/')) return target.pathname + target.search + target.hash;
  }
  return '/app/#home';
}

export async function accountRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/auth/${path}`, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).catch(() => { throw new Error('Could not reach the workspace. Check the connection and try again.'); });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check your details and try again.');
  return data;
}
