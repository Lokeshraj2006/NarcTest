import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { isAdmin, isSupervisor, useAuth } from '../auth';
import { ColourChip, fmt } from './common';

const toDraft = (k) => ({
  name: k.name || '',
  reagent: k.reagent || '',
  read_time_s: k.read_time_s ?? 15,
  max_delta_e: k.max_delta_e ?? 14,
  min_margin: k.min_margin ?? 4,
  outcomes: (k.outcomes || []).map((o) => ({
    label: o.label || '',
    category: o.category || 'NEGATIVE',
    srgb: Array.isArray(o.srgb) ? [...o.srgb] : [128, 128, 128],
  })),
});

function KitEditor({ kit, onSaved, onCancel }) {
  const [d, setD] = useState(() => toDraft(kit));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const set = (k) => (e) => setD((x) => ({ ...x, [k]: e.target.value }));
  const setOut = (i, patch) =>
    setD((x) => ({ ...x, outcomes: x.outcomes.map((o, j) => (j === i ? { ...o, ...patch } : o)) }));
  const setRgb = (i, c, v) =>
    setD((x) => ({
      ...x,
      outcomes: x.outcomes.map((o, j) =>
        j === i ? { ...o, srgb: o.srgb.map((n, k) => (k === c ? v : n)) } : o,
      ),
    }));

  const save = async (e) => {
    e.preventDefault();
    setError(null);
    const outcomes = d.outcomes.map((o) => ({
      label: o.label.trim(),
      category: o.category,
      srgb: o.srgb.map((n) => Math.max(0, Math.min(255, Math.round(Number(n) || 0)))),
    }));
    if (!d.name.trim()) return setError('Please give the kit a name.');
    if (outcomes.length < 2) return setError('A kit needs at least 2 results.');
    if (outcomes.some((o) => !o.label)) return setError('Every result needs a label.');
    setBusy(true);
    try {
      await api.updateKit(kit.id, {
        code: kit.code,
        name: d.name.trim(),
        reagent: d.reagent.trim(),
        read_time_s: Number(d.read_time_s),
        max_delta_e: Number(d.max_delta_e),
        min_margin: Number(d.min_margin),
        is_active: kit.is_active,
        outcomes, // lab is left out, the server works it out from srgb
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card" onSubmit={save}>
      <h3>Edit kit: {kit.code}</h3>
      {error && <div className="alert error">{error}</div>}
      <div className="form-grid">
        <div>
          <label>Name</label>
          <input value={d.name} onChange={set('name')} />
        </div>
        <div>
          <label>Reagent (chemical used)</label>
          <input value={d.reagent} onChange={set('reagent')} />
        </div>
        <div>
          <label>Wait time before photo (seconds)</label>
          <input type="number" min="0" value={d.read_time_s} onChange={set('read_time_s')} />
        </div>
        <div>
          <label>Max colour difference (max_delta_e)</label>
          <input type="number" step="0.5" min="0" value={d.max_delta_e} onChange={set('max_delta_e')} />
        </div>
        <div>
          <label>Min gap between top 2 results (min_margin)</label>
          <input type="number" step="0.5" min="0" value={d.min_margin} onChange={set('min_margin')} />
        </div>
      </div>
      <p className="muted">
        If the colour is further than max_delta_e from every result, or the top two results are
        closer than min_margin, the app says "not sure" instead of guessing.
      </p>

      <h3 style={{ marginTop: 16 }}>Possible results</h3>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th>Label</th>
              <th>Category</th>
              <th>Colour (R, G, B)</th>
              <th>Preview</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {d.outcomes.map((o, i) => (
              <tr key={i}>
                <td>
                  <input value={o.label} onChange={(e) => setOut(i, { label: e.target.value })} />
                </td>
                <td>
                  <select value={o.category} onChange={(e) => setOut(i, { category: e.target.value })}>
                    <option value="POSITIVE">POSITIVE</option>
                    <option value="NEGATIVE">NEGATIVE</option>
                  </select>
                </td>
                <td>
                  <div className="rgb-inputs">
                    {[0, 1, 2].map((c) => (
                      <input
                        key={c}
                        type="number"
                        min="0"
                        max="255"
                        value={o.srgb[c]}
                        onChange={(e) => setRgb(i, c, e.target.value)}
                      />
                    ))}
                  </div>
                </td>
                <td>
                  <ColourChip rgb={o.srgb} size={30} />
                </td>
                <td>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => setD((x) => ({ ...x, outcomes: x.outcomes.filter((_, j) => j !== i) }))}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        className="btn-ghost"
        style={{ marginTop: 8 }}
        onClick={() =>
          setD((x) => ({
            ...x,
            outcomes: [...x.outcomes, { label: '', category: 'NEGATIVE', srgb: [128, 128, 128] }],
          }))
        }
      >
        + Add result
      </button>

      <div className="btn-row" style={{ marginTop: 16 }}>
        <button className="btn-primary" disabled={busy}>
          {busy ? 'Saving...' : 'Save kit'}
        </button>
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function Kits() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [kits, setKits] = useState([]);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setKits(await (isSupervisor(user) ? api.listAllKits() : api.listKits()));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (k) => {
    setError(null);
    try {
      await api.setKitActive(k.id, !k.is_active);
      setMsg(`${k.name} is now ${k.is_active ? 'switched off' : 'switched on'}.`);
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <>
      <div className="topbar">
        <h2>Test Kits</h2>
        <div className="spacer" />
        {!admin && <span className="muted">Only admin can edit kits</span>}
      </div>
      <div className="content">
        {error && <div className="alert error">{error}</div>}
        {msg && <div className="alert ok">{msg}</div>}

        {editing && (
          <KitEditor
            key={editing.id}
            kit={editing}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              setMsg(`Saved ${editing.code}. Version number went up by 1.`);
              setEditing(null);
              load();
            }}
          />
        )}

        {loading ? (
          <div className="empty">Loading kits...</div>
        ) : kits.length === 0 ? (
          <div className="card empty">No kits yet.</div>
        ) : (
          kits.map((k) => (
            <div className="card" key={k.id} style={{ opacity: k.is_active ? 1 : 0.6 }}>
              <div className="panel-head">
                <h3>{k.name}</h3>
                <span className="mono muted">{k.code}</span>
                <span className="badge version">v{k.version}</span>
                {!k.is_active && <span className="badge off">Switched off</span>}
                <div className="spacer" />
                {admin && (
                  <>
                    <label className="switch">
                      <input type="checkbox" checked={!!k.is_active} onChange={() => toggle(k)} /> Active
                    </label>
                    <button className="btn-ghost" onClick={() => setEditing(k)}>
                      Edit
                    </button>
                  </>
                )}
              </div>
              <div className="muted" style={{ marginBottom: 8 }}>
                {k.reagent} - wait {k.read_time_s}s - max diff {k.max_delta_e} - min gap {k.min_margin}
                {k.updated_at && ` - updated ${fmt(k.updated_at)}`}
              </div>
              <div className="outcome-list">
                {(k.outcomes || []).map((o) => (
                  <span key={o.label} className="outcome">
                    <ColourChip rgb={o.srgb} size={20} />
                    <span>{o.label}</span>
                    <span className={`badge ${String(o.category).toLowerCase()}`}>{o.category}</span>
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
}
