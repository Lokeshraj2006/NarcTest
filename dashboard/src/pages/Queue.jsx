import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { saveCsv, stamp } from '../download';

const FILTERS = [
  { key: 'pending_admin_confirmation', label: 'Awaiting review' },
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'notice_generated', label: 'Notice issued' },
  { key: 'rejected', label: 'Rejected' },
  { key: '', label: 'All' },
];

// Worst first — a critical contravention should never sit below a minor one.
const SEVERITY_RANK = { critical: 0, major: 1, moderate: 2, minor: 3 };

const fmt = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';

export default function Queue() {
  const [filter, setFilter] = useState('pending_admin_confirmation');
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listReports(filter || undefined);
      setRows(res.rows || []);
      const all = await api.listReports();
      const tally = {};
      (all.rows || []).forEach((r) => {
        tally[r.status] = (tally[r.status] || 0) + 1;
      });
      setCounts({ ...tally, total: all.total });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const sorted = useMemo(
    () =>
      [...rows].sort((a, b) => {
        const s = (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9);
        return s !== 0 ? s : new Date(b.created_at) - new Date(a.created_at);
      }),
    [rows],
  );

  const exportCsv = () =>
    saveCsv(
      sorted,
      [
        ['Report', (r) => r.report_number],
        ['Status', (r) => r.status.replaceAll('_', ' ')],
        ['Severity', (r) => r.severity],
        ['Product', (r) => r.product_name],
        ['Shop', (r) => r.shop_name],
        ['Manufacturer', (r) => r.manufacturer_name],
        ['Rules cited', (r) => r.violated_rule_count],
        ['Summary', (r) => r.violation_summary],
        ['Inspector', (r) => r.inspector_name],
        ['Badge', (r) => r.inspector_badge],
        ['Scan #', (r) => r.evidence_record_id],
        ['Filed', (r) => r.created_at],
        ['Confirmed', (r) => r.confirmed_at],
        ['Rejected', (r) => r.rejected_at],
      ],
      `FieldProof_violation_reports_${stamp()}.csv`,
    );

  return (
    <>
      <div className="topbar">
        <h2>Violation Queue</h2>
        <div className="spacer" />
        <button className="btn-ghost" onClick={exportCsv} disabled={sorted.length === 0}>
          Export to Excel (CSV)
        </button>
        <button className="btn-ghost" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      <div className="content">
        {error && <div className="alert error">{error}</div>}

        <div className="stat-row">
          <div className="stat">
            <div className="value" style={{ color: 'var(--review)' }}>
              {counts.pending_admin_confirmation || 0}
            </div>
            <div className="label">Awaiting your review</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--compliant)' }}>{counts.confirmed || 0}</div>
            <div className="label">Confirmed</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--primary)' }}>
              {counts.notice_generated || 0}
            </div>
            <div className="label">Notices issued</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--exempt)' }}>{counts.rejected || 0}</div>
            <div className="label">Rejected</div>
          </div>
        </div>

        <div className="btn-row" style={{ marginBottom: 14 }}>
          {FILTERS.map((f) => (
            <button
              key={f.key || 'all'}
              className={filter === f.key ? 'btn-primary' : 'btn-ghost'}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
              {f.key && counts[f.key] ? ` (${counts[f.key]})` : ''}
            </button>
          ))}
        </div>

        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          {loading && rows.length === 0 ? (
            <div className="empty">Loading reports…</div>
          ) : sorted.length === 0 ? (
            <div className="empty">
              <strong>Nothing here.</strong>
              <div style={{ marginTop: 6 }}>
                Reports appear once an inspector files one from the mobile app.
              </div>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Report</th>
                  <th>Severity</th>
                  <th>Product</th>
                  <th>Shop</th>
                  <th>Rules</th>
                  <th>Inspector</th>
                  <th>Filed</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr
                    key={r.id}
                    className="clickable"
                    onClick={() => navigate(`/reports/${r.id}`)}
                  >
                    <td className="mono">{r.report_number}</td>
                    <td><span className={`badge ${r.severity}`}>{r.severity}</span></td>
                    <td>{r.product_name || <span className="muted">unknown</span>}</td>
                    <td>{r.shop_name || <span className="muted">—</span>}</td>
                    <td>{r.violated_rule_count}</td>
                    <td>
                      {r.inspector_name}
                      {r.inspector_badge && (
                        <div className="muted">{r.inspector_badge}</div>
                      )}
                    </td>
                    <td className="muted">{fmt(r.created_at)}</td>
                    <td>
                      <span className={`badge ${r.status}`}>
                        {r.status.replaceAll('_', ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
