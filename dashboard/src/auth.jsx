import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { api, clearSession, getUser, setToken, setUser } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUserState] = useState(getUser);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const login = useCallback(async (username, password) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.login(username, password);
      const profile = {
        id: res.user_id ?? null,
        username: res.username ?? username,
        fullName: res.full_name ?? username,
        role: res.role ?? 'consumer',
      };
      // The dashboard is the Controller's tool. An inspector or consumer
      // signing in here would see an empty, confusing shell, so refuse
      // clearly rather than degrading.
      if (profile.role !== 'admin') {
        clearSession();
        setError(
          `This dashboard is for administrators. '${profile.username}' is a ${profile.role} — ` +
            'please use the mobile app instead.',
        );
        return false;
      }
      setToken(res.access_token);
      setUser(profile);
      setUserState(profile);
      return true;
    } catch (e) {
      setError(e.message || 'Sign in failed.');
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUserState(null);
  }, []);

  const value = useMemo(
    () => ({ user, login, logout, error, busy, setError }),
    [user, login, logout, error, busy],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
};

export function RequireAuth({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}
