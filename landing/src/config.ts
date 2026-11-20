/**
 * Single configurable destination for the "DebateSignal" workspace application.
 * Override at build time with VITE_APP_URL, or use the same-origin /app/ default.
 */
const RAW_APP_URL =
  (import.meta.env.VITE_APP_URL as string | undefined) ||
  '/app/';

export const APP_URL = RAW_APP_URL.endsWith('/')
  ? RAW_APP_URL
  : `${RAW_APP_URL}/`;

export function getWorkspaceUrl(routeHash?: 'home' | 'library' | 'new' | 'room' | 'review'): string {
  if (!routeHash) {
    return `${APP_URL}#home`;
  }
  return `${APP_URL}#${routeHash}`;
}
