/**
 * components/login-page.jsx
 *
 * Login form for SentinelGraph.  In DEMO_MODE the user is automatically
 * logged in and this page is not shown.
 *
 * Styling: uses design-token classes from index.css only — no raw Tailwind
 * palette values.  Labels are linked to inputs via htmlFor/id for a11y.
 */

import React, { useState } from 'react';
import { useAuth } from '@/state/auth-context';
import { Shield, XCircle, Loader2 } from 'lucide-react';

export default function LoginPage() {
  const { login, demoMode } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err.message || 'Login failed. Check credentials and try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-root text-fg-primary">
      <div className="w-full max-w-sm bg-bg-panel border border-border-default rounded p-8 shadow-2xl">

        {/* Brand */}
        <div className="flex flex-col items-center mb-7">
          <div className="w-12 h-12 rounded border border-primary/30 bg-primary-bg flex items-center justify-center mb-3">
            <Shield className="w-6 h-6 text-primary" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-fg-primary">SentinelGraph</h1>
          <p className="text-fg-muted text-[12px] mt-1 font-mono uppercase tracking-widest">Investigative Intelligence</p>
        </div>

        {/* Error banner */}
        {error && (
          <div role="alert" className="flex items-start gap-2 bg-red-bg border border-red/30 text-fg-primary text-[13px] rounded p-3 mb-4">
            <XCircle className="w-4 h-4 text-red shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="sg-username" className="block text-[12px] font-medium text-fg-secondary mb-1.5">
              Username
            </label>
            <input
              id="sg-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-bg-elevated border border-border-default rounded px-3 py-2 text-[13px] text-fg-primary focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-colors"
              placeholder="analyst@domain"
              autoComplete="username"
              autoFocus
              required
            />
          </div>
          <div>
            <label htmlFor="sg-password" className="block text-[12px] font-medium text-fg-secondary mb-1.5">
              Password
            </label>
            <input
              id="sg-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-bg-elevated border border-border-default rounded px-3 py-2 text-[13px] text-fg-primary focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-colors"
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="w-full bg-primary hover:bg-primary-hover disabled:opacity-50 text-primary-fg font-semibold rounded px-4 py-2.5 text-[13px] flex items-center justify-center gap-2 transition-colors cursor-pointer"
          >
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {demoMode && (
          <p className="text-fg-faint text-[11px] text-center mt-5 font-mono">
            DEMO MODE — authentication bypassed
          </p>
        )}
      </div>
    </div>
  );
}