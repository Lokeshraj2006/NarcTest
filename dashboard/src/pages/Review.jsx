import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { ResultBadge, fmt } from './common';
import { TestDetailPanel } from './TestDetail';

export default function Review() {
  const [rows, setRows] = useState([]);
  const [notes, setNotes] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await api.pendingReviews());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (id, decision) => {
    setBusyId(id);
    setError(null);
    setMsg(null);
    try {
      await api.reviewTest(id, decision, notes[id]);
      setMsg(
        decision === 'CONFIRMED'
          ? `Test #${id}: "not sure" result confirmed.`
          : `Test #${id}: retest ordered.`,
      );
      if (open === id) setOpen(null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <div className="topbar">
        <h2>Review "Not sure" tests</h2>
        <div className="spacer" />
        <button className="btn-ghost" onClick={load}>Refresh</button>
      </div>
      <div className="content">
        <div className="alert info">
          These tests could not be read clearly, so the app did not guess. Check the photo, then
          either confirm the "not sure" result or ask the officer to do the test again.
        </div>
        {error && <div className="alert error">{error}</div>}
        {msg && <div className="alert ok">{msg}</div>}

        {loading ? (
          <div className="empty">Loading...</div>
        ) : rows.length === 0 ? (
          <div className="card empty">Nothing to review right now. All clear!</div>
        ) : (
          rows.map((t) => (
            <div className="card" key={t.id}>
              <div className="panel-head">
                <h3>Test #{t.id}</h3>
                <ResultBadge result={t.result || 'INCONCLUSIVE'} />
                <span className="muted">{fmt(t.created_at)}</span>
                <div className="spacer" />
                <button className="linkish" onClick={() => setOpen(open === t.id ? null : t.id)}>
                  {open === t.id ? 'Hide photo & details' : 'See photo & details'}
                </button>
              </div>
              <div className="muted" style={{ marginBottom: 8 }}>
                Officer: {t.officer_name || t.officer_id} - Kit: {t.kit_name || t.kit_code}
              </div>
              <div style={{ marginBottom: 8 }}>
                <strong>Why not sure:</strong> {t.reason || 'No reason given'}
              </div>
              {open === t.id && <TestDetailPanel testId={t.id} />}
              <label>Note (optional)</label>
              <textarea
                value={notes[t.id] || ''}
                onChange={(e) => setNotes((n) => ({ ...n, [t.id]: e.target.value }))}
                placeholder="E.g. Photo was too dark, please redo the test."
              />
              <div className="btn-row" style={{ marginTop: 10 }}>
                <button
                  className="btn-primary"
                  disabled={busyId === t.id}
                  onClick={() => decide(t.id, 'CONFIRMED')}
                >
                  Confirm "not sure"
                </button>
                <button
                  className="btn-danger"
                  disabled={busyId === t.id}
                  onClick={() => decide(t.id, 'RETEST')}
                >
                  Order retest
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
}
