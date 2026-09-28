import { Component, useEffect, useState } from 'react';
import { NavLink, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { API_BASE, api } from './api';
import { RequireAuth, isSupervisor, useAuth } from './auth';
import Kits from './pages/Kits';
import Login from './pages/Login';
import Review from './pages/Review';
import TestDetail from './pages/TestDetail';
import TestLog from './pages/TestLog';
import TestMap from './pages/TestMap';
import Verify from './pages/Verify';

/**
 * Without this, any render error produces a blank white page with the cause
 * buried in the console. Showing it on screen makes failures debuggable.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{ padding: 32, fontFamily: 'system-ui, sans-serif' }}>
        <h2 style={{ color: '#dc2626', marginTop: 0 }}>Oops, the page crashed</h2>
        <p>Something went wrong. Details for the tech team:</p>
        <pre
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 8,
            padding: 14,
            overflowX: 'auto',
            fontSize: 12.5,
          }}
        >
          {String(this.state.error?.stack || this.state.error)}
        </pre>
        <button
          onClick={() => window.location.assign('/login')}
          style={{
            marginTop: 12,
            padding: '8px 14px',
            borderRadius: 7,
            border: 0,
            background: '#0f766e',
            color: '#fff',
            cursor: 'pointer',
          }}
        >
          Back to sign in
        </button>
      </div>
    );
  }
}

const ROLE_NAMES = { field_officer: 'Field officer', supervisor: 'Supervisor', admin: 'Admin' };

function Sidebar({ pendingCount }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const sup = isSupervisor(user);

  const signOut = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <h1>FieldProof</h1>
        <span>Field Drug Testing - Supervisor Dashboard</span>
      </div>

      <NavLink to="/tests" className="nav-link">Test Log</NavLink>
      <NavLink to="/map" className="nav-link">Map</NavLink>
      <NavLink to="/kits" className="nav-link">Kits</NavLink>
      {sup && (
        <NavLink to="/review" className="nav-link">
          Review
          {pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
        </NavLink>
      )}

      <div className="sidebar-footer">
        <div style={{ marginBottom: 4 }}>{user?.fullName}</div>
        <div style={{ fontSize: 11, marginBottom: 10 }}>
          {user?.username} - {ROLE_NAMES[user?.role] || user?.role}
        </div>
        <button
          className="btn-ghost"
          style={{ width: '100%', color: '#cbd5e1', borderColor: '#334155' }}
          onClick={signOut}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}

/** Layout route: renders the matched page through <Outlet />. */
function Shell() {
  const { user } = useAuth();
  const sup = isSupervisor(user);
  const [pendingCount, setPendingCount] = useState(0);

  // Poll the review list so the badge stays fresh.
  useEffect(() => {
    if (!sup) return undefined;
    let alive = true;
    const load = async () => {
      try {
        const rows = await api.pendingReviews();
        if (alive) setPendingCount(rows.length);
      } catch {
        /* badge is not critical */
      }
    };
    load();
    const t = setInterval(load, 20000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [sup]);

  return (
    <div className="shell">
      <Sidebar pendingCount={pendingCount} />
      <div className="main">
        <Outlet />
      </div>
    </div>
  );
}

function SupervisorOnly({ children }) {
  const { user } = useAuth();
  if (!isSupervisor(user)) return <Navigate to="/tests" replace />;
  return children;
}

export default function App() {
  const [backendUp, setBackendUp] = useState(null);
  const isPublic = useLocation().pathname.startsWith('/verify/');

  useEffect(() => {
    api.health().then(() => setBackendUp(true)).catch(() => setBackendUp(false));
  }, []);

  return (
    <ErrorBoundary>
      {backendUp === false && !isPublic && (
        <div className="alert error" style={{ margin: 0, borderRadius: 0 }}>
          Cannot reach the server at <strong>{API_BASE}</strong>. Start it with{' '}
          <span className="mono">python -m uvicorn app.main:app --port 8000</span> from
          the backend folder.
        </div>
      )}

      {/* One flat route table. A layout route renders Shell with an Outlet,
          which avoids nesting <Routes> inside a splat route — React Router v6
          rejects absolute child paths in that arrangement. */}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/verify/:id" element={<Verify />} />
        <Route
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route path="/tests" element={<TestLog />} />
          <Route path="/tests/:id" element={<TestDetail />} />
          <Route path="/map" element={<TestMap />} />
          <Route path="/kits" element={<Kits />} />
          <Route
            path="/review"
            element={
              <SupervisorOnly>
                <Review />
              </SupervisorOnly>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/tests" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
