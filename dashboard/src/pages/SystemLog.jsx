import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { saveBlob, saveCsv, stamp } from '../download';
import ExtraPhotos from '../ExtraPhotos';

const fmt = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';

const words = (s) => (s || '').replaceAll('_', ' ');

/**
 * Every scan in the system, consumer and inspector alike.
 *
 * This is the Controller's "what is happening in the field" view, distinct
 * from the Violation Queue which only holds reports an inspector escalated.
 * Each scan names who took it and flags a rescan, a re-used photo, or label
 * fields changed from what OCR read. Nothing here edits a scan.
 */
export default function SystemLog() {
  const [rows, setRows] = useState([]);
  const [onlyAction, setOnlyAction] = useState(false);
  const [person, setPerson] = useState('');
  const [query, setQuery] = useState('');
  const [detail, setDetail] = useState(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.inspectionLog(onlyAction);
      setRows(res.rows || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [onlyAction]);

  useEffect(() => {
    load();
  }, [load]);

  const open = async (evidenceId) => {
    setDetail({ loading: true });
    try {
      setDetail(await api.inspectionDetail(evidenceId));
    } catch (e) {
      setDetail(null);
      setError(e.message);
    }
  };

  const people = useMemo(() => {
    const roleByName = new Map();
    rows.forEach((r) => {
      if (r.captured_by_username) roleByName.set(r.captured_by_username, r.captured_by_role);
    });
    return [...roleByName.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [rows]);

  // Search by product, barcode, scan number, complaint number or who scanned.
  const q = query.trim().toLowerCase().replace(/^#/, '');
  const matches = (r) =>
    !q ||
    [
      r.product_name,
      r.barcode,
      String(r.evidence_record_id),
      r.complaint_number,
      r.captured_by_username,
    ].some((v) => v && String(v).toLowerCase().includes(q));
  const shown = rows.filter(
    (r) => (!person || r.captured_by_username === person) && matches(r),
  );
  const actionNeeded = shown.filter((r) => r.overall_status === 'action_needed').length;
  const needsReview = shown.filter((r) => r.overall_status === 'needs_review').length;

  const exportCsv = () =>
    saveCsv(
      shown,
      [
        ['Scan #', (r) => r.evidence_record_id],
        ['Product', (r) => r.product_name],
        ['Barcode', (r) => r.barcode],
        ['Status', (r) => words(r.overall_status)],
        ['Reason', (r) => r.action_reason],
        ['Scanned by', (r) => r.captured_by_username],
        ['Role', (r) => r.captured_by_role],
        ['When', (r) => r.timestamp],
        ['Latitude', (r) => r.gps_latitude],
        ['Longitude', (r) => r.gps_longitude],
        ['Complaint', (r) => r.complaint_number],
        ['Complaint status', (r) => words(r.complaint_status)],
        ['Edited fields', (r) => (r.edited_fields || []).map(words).join('; ')],
      ],
      `FieldProof_scans_${stamp()}.csv`,
    );

  const downloadReport = async (evidenceId) => {
    setPdfBusy(true);
    setError(null);
    try {
      saveBlob(await api.complianceReportPdf(evidenceId), `FieldProof_compliance_report_scan${evidenceId}.pdf`);
    } catch (e) {
      setError(e.message);
    } finally {
      setPdfBusy(false);
    }
  };

  return (
    <>
      <div className="topbar">
        <h2>System Log</h2>
        <div className="spacer" />
        <input
          type="search"
          id="scan-search"
          aria-label="Search scans"
          placeholder="Search product, barcode, scan # or complaint"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ maxWidth: 300 }}
        />
        <select
          aria-label="Scanned by"
          value={person}
          onChange={(e) => setPerson(e.target.value)}
          style={{ maxWidth: 230 }}
        >
          <option value="">Everyone</option>
          {people.map(([name, role]) => (
            <option key={name} value={name}>
              {name} ({role})
            </option>
          ))}
        </select>
        <button
          className={onlyAction ? 'btn-primary' : 'btn-ghost'}
          onClick={() => setOnlyAction((v) => !v)}
        >
          Action needed only
        </button>
        <button className="btn-ghost" onClick={exportCsv} disabled={shown.length === 0}>
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
            <div className="value">{shown.length}</div>
            <div className="label">Scans shown</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--violation)' }}>{actionNeeded}</div>
            <div className="label">Action needed</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--review)' }}>{needsReview}</div>
            <div className="label">Needs review</div>
          </div>
          <div className="stat">
            <div className="value" style={{ color: 'var(--compliant)' }}>
              {shown.length - actionNeeded - needsReview}
            </div>
            <div className="label">Compliant</div>
          </div>
        </div>

        <div className="two-col">
          <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
            {shown.length === 0 && !loading ? (
              <div className="empty">
                {rows.length === 0 ? 'No scans recorded yet.' : 'No scans match your search.'}
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Scanned by</th>
                    <th>When</th>
                    <th>Location</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <tr
                      key={r.evidence_record_id}
                      className="clickable"
                      onClick={() => open(r.evidence_record_id)}
                    >
                      <td>
                        {r.product_name || `Evidence #${r.evidence_record_id}`}
                        <span className="muted"> · #{r.evidence_record_id}</span>
                        {r.action_reason && (
                          <div className="muted" style={{ marginTop: 3 }}>
                            {r.action_reason.slice(0, 90)}
                            {r.action_reason.length > 90 ? '…' : ''}
                          </div>
                        )}
                        <Flags row={r} />
                      </td>
                      <td>
                        {r.captured_by_username || '—'}
                        {r.captured_by_role && <div className="muted">{r.captured_by_role}</div>}
                      </td>
                      <td className="muted">{fmt(r.timestamp)}</td>
                      <td className="muted mono">
                        {r.gps_latitude != null
                          ? `${r.gps_latitude.toFixed(4)}, ${r.gps_longitude.toFixed(4)}`
                          : '—'}
                      </td>
                      <td>
                        <span className={`badge ${r.overall_status}`}>
                          {words(r.overall_status)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card">
            <h3>Scan detail</h3>
            {!detail ? (
              <div className="muted">Select a scan to see all 13 rule checks.</div>
            ) : detail.loading ? (
              <div className="muted">Loading…</div>
            ) : (
              <>
                <button
                  className="btn-primary"
                  style={{ marginBottom: 12 }}
                  onClick={() => downloadReport(detail.evidence_record_id)}
                  disabled={pdfBusy}
                >
                  {pdfBusy ? 'Preparing…' : 'Download compliance report (PDF)'}
                </button>
                <dl className="kv" style={{ marginBottom: 12 }}>
                  <dt>Scan</dt><dd>#{detail.evidence_record_id}</dd>
                  <dt>Product</dt><dd>{detail.product_name || '—'}</dd>
                  <dt>Barcode</dt>
                  <dd>
                    {detail.barcode || '—'}
                    {detail.barcode_source && (
                      <span className="muted"> · read by the {detail.barcode_source === 'server' ? 'server' : 'phone'}</span>
                    )}
                  </dd>
                  <dt>Status</dt>
                  <dd>
                    <span className={`badge ${detail.overall_status}`}>
                      {words(detail.overall_status)}
                    </span>
                  </dd>
                  <dt>Checks</dt>
                  <dd>{detail.failed_checks} failed of {detail.total_checks}</dd>
                  <dt>Authenticity</dt>
                  <dd>{words(detail.authenticity?.status) || '—'}</dd>
                  <dt>FSSAI mark</dt>
                  <dd>
                    {words(detail.fssai_mark?.status) || '—'}
                    {detail.fssai_mark?.photo > 0 && (
                      <span className="muted"> · read on extra photo {detail.fssai_mark.photo}</span>
                    )}
                    {detail.fssai_mark?.photos_checked > 1 && detail.fssai_mark?.status === 'not_found' && (
                      <div className="muted">{detail.fssai_mark.message}</div>
                    )}
                  </dd>
                  <dt>Scanned by</dt>
                  <dd>
                    {detail.captured_by_username
                      ? `${detail.captured_by_username} (${detail.captured_by_role})`
                      : '—'}
                  </dd>
                  <dt>Complaint</dt>
                  <dd>
                    {detail.complaint_number
                      ? `${detail.complaint_number} · ${words(detail.complaint_status)}`
                      : '—'}
                  </dd>
                  {detail.rescan_of_id != null && (
                    <>
                      <dt>Rescan of</dt>
                      <dd><ScanLinks ids={[detail.rescan_of_id]} open={open} /></dd>
                    </>
                  )}
                  {detail.rescan_ids?.length > 0 && (
                    <>
                      <dt>Rescanned as</dt>
                      <dd><ScanLinks ids={detail.rescan_ids} open={open} /></dd>
                    </>
                  )}
                  {detail.duplicate_of_id != null && (
                    <>
                      <dt>Same photo as</dt>
                      <dd><ScanLinks ids={[detail.duplicate_of_id]} open={open} /></dd>
                    </>
                  )}
                  {detail.same_photo_ids?.length > 0 && (
                    <>
                      <dt>Photo re-used in</dt>
                      <dd><ScanLinks ids={detail.same_photo_ids} open={open} /></dd>
                    </>
                  )}
                  <dt>Edited fields</dt>
                  <dd><EditedFields fields={detail.edited_fields} /></dd>
                  <dt>GPS accuracy</dt>
                  <dd>
                    {detail.evidence?.gps_accuracy_meters != null
                      ? `± ${Math.round(detail.evidence.gps_accuracy_meters)} m`
                      : '—'}
                  </dd>
                  <dt>SHA-256</dt>
                  <dd className="mono" style={{ wordBreak: 'break-all', fontSize: 10.5 }}>
                    {detail.evidence?.sha256_hash || '—'}
                  </dd>
                </dl>

                <ExtraPhotos
                  evidenceId={detail.evidence_record_id}
                  photos={detail.extra_photos}
                  markPhoto={detail.fssai_mark?.photo}
                />

                <table>
                  <tbody>
                    {(detail.rule_checks || []).map((rc) => (
                      <tr key={rc.id}>
                        <td style={{ width: 30 }}>{rc.rule_number}</td>
                        <td>
                          {rc.rule_name}
                          {rc.failure_reason && (
                            <div className="muted" title={rc.failure_reason}>
                              {rc.failure_reason.length > 140
                                ? `${rc.failure_reason.slice(0, 140)}…`
                                : rc.failure_reason}
                            </div>
                          )}
                          {rc.scale_mm_per_px != null && (
                            <div className="muted">
                              Measured {rc.detected_value ?? '—'} · scale{' '}
                              {rc.scale_mm_per_px.toFixed(3)} mm per pixel, from the{' '}
                              {barcodeName(rc.scale_reference)} barcode
                            </div>
                          )}
                        </td>
                        <td style={{ width: 70 }}>
                          <span className={`badge ${rc.status.toLowerCase()}`}>{rc.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

const BARCODE_NAMES = { ean13: 'EAN-13', ean8: 'EAN-8', upca: 'UPC-A', upce: 'UPC-E' };

/** "ean13" -> "EAN-13", for the Rule 9 scale line. */
function barcodeName(reference) {
  return BARCODE_NAMES[reference] || (reference ? reference.toUpperCase() : 'retail');
}

/** Audit context for one scan: rescan, re-used photo, edited fields, complaint. */
function Flags({ row }) {
  const flags = [];
  if (row.rescan_of_id != null) {
    flags.push(<span key="rescan" className="flag">rescan of #{row.rescan_of_id}</span>);
  }
  if (row.duplicate_of_id != null) {
    flags.push(
      <span key="photo" className="flag warn">same photo as #{row.duplicate_of_id}</span>,
    );
  }
  if (row.edited_fields?.length) {
    flags.push(
      <span key="edited" className="flag warn">
        edited: {row.edited_fields.map(words).join(', ')}
      </span>,
    );
  }
  if (row.complaint_number) {
    flags.push(
      <span key="complaint" className="flag">
        {row.complaint_number} · {words(row.complaint_status)}
      </span>,
    );
  }
  return flags.length ? <div>{flags}</div> : null;
}

function ScanLinks({ ids, open }) {
  return ids.map((id, i) => (
    <span key={id}>
      {i > 0 && ', '}
      <button type="button" className="linkish" onClick={() => open(id)}>
        #{id}
      </button>
    </span>
  ));
}

function EditedFields({ fields }) {
  if (fields == null) {
    return <span className="muted">Not recorded (scanned before edit tracking)</span>;
  }
  if (fields.length === 0) return 'None — submitted as OCR read it';
  return (
    <ul className="edits">
      {fields.map((e) => (
        <li key={e.field}>
          <strong>{words(e.field)}</strong>: {String(e.extracted ?? '(blank)')} →{' '}
          {String(e.submitted ?? '(blank)')}
        </li>
      ))}
    </ul>
  );
}
