/**
 * state/auth-context.jsx
 *
 * Provides AuthProvider + useAuth to the React tree.
 * In SENTINELGRAPH_DEMO_MODE the user is automatically "logged in" with a
 * synthetic demo token.  When the backend requires real authentication the
 * user must provide username + password via the login form.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  getToken,
  setToken,
  clearToken,
  getUser,
  setUser,
  loginRequest,
  detectDemoMode,
  isAuthenticated,
} from '@/api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoMode] = useState(false);
  const [token, setLocalToken] = useState(() => getToken());
  const [user, setLocalUser] = useState(() => getUser());

  // On mount: detect demo mode and bootstrap session.
  useEffect(() => {
    (async () => {
      const isDemo = await detectDemoMode();
      setDemoMode(isDemo);
      if (isDemo && !isAuthenticated()) {
        // In demo mode, auto-login with synthetic credentials.
        try {
          const resp = await loginRequest('demo', 'demo');
          setToken(resp.access_token);
          setLocalToken(resp.access_token);
          const u = { username: 'demo', is_demo: true };
          setUser(u);
          setLocalUser(u);
        } catch {
          // Backend may be down; proceed without token.
        }
      }
      setLoading(false);
    })();
  }, []);

  const login = useCallback(async (username, password) => {
    const resp = await loginRequest(username, password);
    setToken(resp.access_token);
    setLocalToken(resp.access_token);
    const u = { username, is_demo: false };
    setUser(u);
    setLocalUser(u);
    return resp;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setLocalToken(null);
    setLocalUser(null);
  }, []);

  const value = { loading, token, user, demoMode, login, logout };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
