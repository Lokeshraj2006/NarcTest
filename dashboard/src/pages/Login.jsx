import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { API_BASE } from '../api';
import { useAuth } from '../auth';

export default function Login() {
  const { user, login, error, busy } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const location = useLocation();

  if (user) {
    const to = location.state?.from?.pathname || '/queue';
    return <Navigate to={to} replace />;
  }

  const submit = async (e) => {
    e.preventDefault();
    const ok = await login(username.trim(), password);
    if (ok) navigate(location.state?.from?.pathname || '/queue', { replace: true });
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>FieldProof</h1>
        <div className="sub">Supervisor / Admin sign in</div>

        {error && <div className="alert error">{error}</div>}

        <label htmlFor="u">Username or email</label>
        <input
          id="u"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoFocus
          required
        />

        <label htmlFor="p">Password</label>
        <input
          id="p"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />

        <button
          className="btn-primary"
          style={{ width: '100%', marginTop: 18 }}
          disabled={busy || !username || !password}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <div className="muted" style={{ marginTop: 16, textAlign: 'center' }}>
          Inspectors and consumers use the mobile app.
          <br />
          <span className="mono" style={{ fontSize: 10.5 }}>{API_BASE}</span>
        </div>
      </form>
    </div>
  );
}
