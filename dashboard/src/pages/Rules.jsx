import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

const CATEGORY_LABEL = {
  declaration: 'Declaration — what must appear',
  presentation: 'Presentation — how it must appear',
  statutory: 'Statutory — licences & registrations',
};

/**
 * The 13 compliance rules, read live from the database rather than
 * hard-coded here — so what the Controller sees is exactly what the
 * compliance rules enforce.
 */
export default function Rules() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await api.listRules());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (rule) => {
    setBusyId(rule.id);
    setError(null);
    try {
      await api.updateRule(rule.id, { is_active: !rule.is_active });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const grouped = (data?.rules || []).reduce((acc, r) => {
    (acc[r.category] ||= []).push(r);
    return acc;
  }, {});

  return (
    <>
      <div className="topbar">
        <h2>Rule Catalogue</h2>
        <div className="spacer" />
        <button className="btn-ghost" onClick={load}>Refresh</button>
      </div>

      <div className="content">
        {error && <div className="alert error">{error}</div>}

        {data && (
          <div className="stat-row">
            <div className="stat">
              <div className="value">{data.total}</div>
              <div className="label">Rules defined</div>
            </div>
            <div className="stat">
              <div className="value" style={{ color: 'var(--compliant)' }}>{data.active}</div>
              <div className="label">Active</div>
            </div>
            <div className="stat">
              <div className="value" style={{ color: 'var(--review)' }}>{data.cv_dependent}</div>
              <div className="label">Need CV measurement</div>
            </div>
          </div>
        )}

        <div className="alert info">
          Rules marked <strong>needs measurement</strong> are measured from the photo,
          with the barcode used as a ruler for letter size. When a photo can't be
          measured they return <strong>REVIEW</strong>, not a guessed PASS, and a
          letter size under the limit is <strong>REVIEW</strong> too, for a person to
          measure on the pack. Switching a rule off makes new scans record it as{' '}
          <strong>EXEMPT</strong>, so it can't raise a complaint; earlier scans keep
          their results.
        </div>

        {!data ? (
          <div className="empty">Loading rules…</div>
        ) : (
          Object.entries(grouped).map(([category, rules]) => (
            <div className="card" key={category} style={{ padding: 0 }}>
              <h3 style={{ padding: '14px 16px 0' }}>
                {CATEGORY_LABEL[category] || category}
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: 40 }}>#</th>
                      <th>Rule</th>
                      <th>Statutory provision</th>
                      <th style={{ width: 90 }}>Severity</th>
                      <th style={{ width: 110 }}>State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((r) => (
                      <tr key={r.id}>
                        <td><strong>{r.rule_number}</strong></td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{r.rule_name}</div>
                          <div className="muted" style={{ marginTop: 3 }}>{r.description}</div>
                          <div className="muted mono" style={{ marginTop: 3 }}>
                            {r.rule_code}
                            {r.requires_cv && (
                              <span className="badge review" style={{ marginLeft: 8 }}>
                                needs measurement
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="muted">{r.statutory_reference}</td>
                        <td><span className={`badge ${r.default_severity}`}>{r.default_severity}</span></td>
                        <td>
                          <button
                            className={r.is_active ? 'btn-ghost' : 'btn-primary'}
                            disabled={busyId === r.id}
                            onClick={() => toggle(r)}
                            style={{ fontSize: 12, padding: '5px 10px' }}
                          >
                            {busyId === r.id ? '…' : r.is_active ? 'Active' : 'Disabled'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
}
