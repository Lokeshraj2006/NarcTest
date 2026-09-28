import { Component, useEffect, useState } from 'react';
import { NavLink, Navigate, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import { API_BASE, api } from './api';
import { RequireAuth, useAuth } from './auth';
import Login from './pages/Login';
import MapView from './pages/MapView';
import Queue from './pages/Queue';
import ReportDetail from './pages/ReportDetail';
import Rules from './pages/Rules';
import SystemLog from './pages/SystemLog';

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
        <h2 style={{ color: '#dc2626', marginTop: 0 }}>Dashboard error</h2>
        <p>Something failed while rendering. The details:</p>
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
            background: '#1e3a8a',
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

function Sidebar({ pendingCount }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const signOut = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <h1>FieldProof</h1>
        <span>Field Drug Testing Dashboard</span>
      </div>

      <NavLink to="/queue" className="nav-link">
        Violation Queue
        {pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
      </NavLink>
      <NavLink to="/map" className="nav-link">Map</NavLink>
      <NavLink to="/log" className="nav-link">System Log</NavLink>
      <NavLink to="/rules" className="nav-link">Rule Catalogue</NavLink>

      <div className="sidebar-footer">
        <div style={{ marginBottom: 4 }}>{user?.fullName}</div>
        <div style={{ fontSize: 11, marginBottom: 10 }}>{user?.username} · admin</div>
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

/** Layout route — renders the matched child page through <Outlet />. */
function Shell() {
  const [pendingCount, setPendingCount] = useState(0);

  // Poll the pending queue so the badge reflects newly filed reports without
  // the Controller needing to refresh. Cheap query, 20s is plenty.
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await api.listReports('pending_admin_confirmation');
        if (alive) setPendingCount(res.total ?? 0);
      } catch {
        /* badge is non-critical; page-level errors surface elsewhere */
      }
    };
    load();
    const t = setInterval(load, 20000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <div className="shell">
      <Sidebar pendingCount={pendingCount} />
      <div className="main">
        <Outlet />
      </div>
    </div>
  );
}

export default function App() {
  const [backendUp, setBackendUp] = useState(null);

  useEffect(() => {
    api.health().then(() => setBackendUp(true)).catch(() => setBackendUp(false));
  }, []);

  return (
    <ErrorBoundary>
      {backendUp === false && (
        <div className="alert error" style={{ margin: 0, borderRadius: 0 }}>
          Cannot reach the backend at <strong>{API_BASE}</strong>. Start it with{' '}
          <span className="mono">python -m uvicorn app.main:app --port 8000</span> from
          the Backend folder.
        </div>
      )}

      {/* One flat route table. A layout route renders Shell with an Outlet,
          which avoids nesting <Routes> inside a splat route — React Router v6
          rejects absolute child paths in that arrangement. */}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route path="/queue" element={<Queue />} />
          <Route path="/reports/:id" element={<ReportDetail />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/log" element={<SystemLog />} />
          <Route path="/rules" element={<Rules />} />
        </Route>
        <Route path="*" element={<Navigate to="/queue" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
