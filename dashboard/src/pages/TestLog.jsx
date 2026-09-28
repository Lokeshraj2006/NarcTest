import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { isSupervisor, useAuth } from '../auth';
import { saveBlob, saveCsv, stamp } from '../download';
import { ResultBadge, fmt } from './common';
import { TestDetailPanel } from './TestDetail';

const EMPTY = { date_from: '', date_to: '', officer_id: '', kit_id: '', result: '', q: '' };

export default function TestLog() {
  const { user } = useAuth();
  const [filters, setFilters] = useState(EMPTY);
  const [tests, setTests] = useState([]);
  const [kits, setKits] = useState([]);
  const [officers, setOfficers] = useState({});
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (f) => {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.listTests(f);
      setTests(rows);
      // Remember every officer we have seen so the dropdown keeps them.
      setOfficers((old) => {
        const next = { ...old };
        rows.forEach((t) => {
          if (t.officer_id != null) next[t.officer_id] = t.officer_name || `Officer ${t.officer_id}`;
        });
        return next;
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(EMPTY);
    (isSupervisor(user) ? api.listAllKits() : api.listKits()).then(setKits).catch(() => {});
  }, [load, user]);

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));
  const apply = (e) => {
    e.preventDefault();
    load(filters);
  };
  const clear = () => {
    setFilters(EMPTY);
    load(EMPTY);
  };

  const counts = useMemo(() => {
    const c = { POSITIVE: 0, NEGATIVE: 0, INCONCLUSIVE: 0 };
    tests.forEach((t) => {
      if (c[t.result] != null) c[t.result] += 1;
    });
    return c;
  }, [tests]);

  const exportCsv = async () => {
    try {
      if (isSupervisor(user)) {
        saveBlob(await api.exportCsv(filters), `fieldproof-tests-${stamp()}.csv`);
        return;
      }
    } catch {
      /* fall back to a CSV made from the table */
    }
    saveCsv(
      tests,
      [
        ['Test ID', (t) => t.id],
        ['Time', (t) => t.created_at],
        ['Officer', (t) => t.officer_name],
        ['Kit', (t) => t.kit_name],
        ['Result', (t) => t.result],
        ['Outcome', (t) => t.outcome_label],
        ['Confidence', (t) => t.confidence],
        ['Reason', (t) => t.reason],
        ['Latitude', (t) => t.latitude],
        ['Longitude', (t) => t.longitude],
        ['Photo SHA-256', (t) => t.image_sha256],
        ['Record hash', (t) => t.record_hash],
      ],
      `fieldproof-tests-${stamp()}.csv`,
    );
  };

  return (
    <>
      <div className="topbar">
        <h2>Test Log</h2>
        <div className="spacer" />
        <button className="btn-ghost" onClick={exportCsv} disabled={!tests.length}>
          Download CSV
        </button>
      </div>

      <div className="content">
        <div className="stat-row">
          <div className="stat">
            <div className="value">{tests.length}</div>
            <div className="label">Tests shown</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--positive)' }}>{counts.POSITIVE}</div>
            <div className="label">Positive</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--negative)' }}>{counts.NEGATIVE}</div>
            <div className="label">Negative</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--inconclusive)' }}>{counts.INCONCLUSIVE}</div>
            <div className="label">Not sure</div>
          </div>
        </div>

        <form className="card filters" onSubmit={apply}>
          <div>
            <label>From date</label>
            <input type="date" value={filters.date_from} onChange={set('date_from')} />
          </div>
          <div>
            <label>To date</label>
            <input type="date" value={filters.date_to} onChange={set('date_to')} />
          </div>
          <div>
            <label>Officer</label>
            <select value={filters.officer_id} onChange={set('officer_id')}>
              <option value="">All officers</option>
              {Object.entries(officers).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Kit</label>
            <select value={filters.kit_id} onChange={set('kit_id')}>
              <option value="">All kits</option>
              {kits.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Result</label>
            <select value={filters.result} onChange={set('result')}>
              <option value="">All results</option>
              <option value="POSITIVE">Positive</option>
              <option value="NEGATIVE">Negative</option>
              <option value="INCONCLUSIVE">Not sure</option>
            </select>
          </div>
          <div>
            <label>Search</label>
            <input placeholder="Type anything..." value={filters.q} onChange={set('q')} />
          </div>
          <div className="btn-row filter-btns">
            <button className="btn-primary" type="submit">Search</button>
            <button className="btn-ghost" type="button" onClick={clear}>Clear</button>
          </div>
        </form>

        {error && <div className="alert error">{error}</div>}

        <div className={selected ? 'split' : ''}>
          <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
            {loading ? (
              <div className="empty">Loading tests...</div>
            ) : tests.length === 0 ? (
              <div className="empty">No tests found. Try clearing the filters.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Time</th>
                    <th>Officer</th>
                    <th>Kit</th>
                    <th>Result</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {tests.map((t) => (
                    <tr
                      key={t.id}
                      className={`clickable ${selected === t.id ? 'selected' : ''}`}
                      onClick={() => setSelected(t.id)}
                    >
                      <td>{t.id}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>{fmt(t.created_at)}</td>
                      <td>{t.officer_name || t.officer_id}</td>
                      <td>{t.kit_name || t.kit_code}</td>
                      <td>
                        <ResultBadge result={t.result} />
                      </td>
                      <td className="muted">
                        {t.outcome_label || t.reason || ''}
                        {t.confidence != null && ` (${t.confidence}% sure)`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {selected && <TestDetailPanel testId={selected} onClose={() => setSelected(null)} />}
        </div>
      </div>
    </>
  );
}
