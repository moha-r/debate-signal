import { useState } from 'react';
import { ArrowRight, Menu, X } from 'lucide-react';
import { getWorkspaceUrl } from '../config';

const NAV_LINKS = [
  { label: 'Features', href: '#features' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Example', href: '#example' },
  { label: 'FAQ', href: '#faq' },
];

interface NavbarProps {
  onOpenLogin: () => void;
}

export function Navbar({ onOpenLogin }: NavbarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const workspaceUrl = getWorkspaceUrl('home');

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-[#D4D9E6]/80 bg-[#FCFBFE]/92">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-8 px-4 sm:px-6 lg:px-8">
        {/* Zone 1: Single-line brand mark + wordmark */}
        <a
          href="#top"
          className="flex shrink-0 items-center gap-2.5 whitespace-nowrap text-base font-semibold tracking-tight text-[#1E1934]"
        >
          <span
            className="pearl-mini inline-block h-5 w-5 shrink-0 rounded-full ring-1 ring-[#D4D9E6]"
            aria-hidden="true"
          />
          <span>DebateSignal</span>
        </a>

        {/* Zone 2: Clean single-line navigation links */}
        <nav
          className="hidden items-center gap-7 md:flex"
          aria-label="Primary navigation"
        >
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="whitespace-nowrap shrink-0 text-sm font-medium text-[#524B6B] transition-colors hover:text-[#604CB5]"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Zone 3: Log in + Primary CTA + mobile menu toggle */}
        <div className="flex shrink-0 items-center gap-2.5">
          <button
            type="button"
            onClick={onOpenLogin}
            className="btn-secondary hidden min-h-[38px] items-center whitespace-nowrap shrink-0 rounded-[11px] px-3.5 py-1.5 text-sm font-medium md:inline-flex"
          >
            Log in
          </button>

          <a
            href={workspaceUrl}
            className="btn-primary hidden min-h-[38px] items-center gap-1.5 whitespace-nowrap shrink-0 rounded-[11px] px-4 py-1.5 text-sm font-medium md:inline-flex"
          >
            <span>Open workspace</span>
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </a>

          <button
            type="button"
            onClick={() => setMobileOpen((prev) => !prev)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-[11px] border border-[#D4D9E6] bg-white text-[#1E1934] md:hidden"
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav-drawer"
            aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
          >
            {mobileOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div
          id="mobile-nav-drawer"
          className="border-t border-[#D4D9E6]/85 bg-white px-4 py-4 md:hidden"
        >
          <nav className="flex flex-col gap-1" aria-label="Mobile navigation">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="flex min-h-[44px] items-center rounded-lg px-3 text-sm font-medium text-[#1E1934] hover:bg-[#F3EFFB]"
              >
                {link.label}
              </a>
            ))}
            <button
              type="button"
              onClick={() => {
                setMobileOpen(false);
                onOpenLogin();
              }}
              className="btn-secondary mt-2 flex min-h-[44px] items-center justify-center rounded-[11px] px-4 py-2.5 text-sm font-medium"
            >
              Log in
            </button>
            <a
              href={workspaceUrl}
              onClick={() => setMobileOpen(false)}
              className="btn-primary mt-2 flex min-h-[44px] items-center justify-center gap-2 rounded-[11px] px-4 py-2.5 text-sm font-medium"
            >
              <span>Open workspace</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}
