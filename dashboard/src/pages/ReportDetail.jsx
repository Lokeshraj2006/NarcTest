import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { saveBlob } from '../download';
import ExtraPhotos from '../ExtraPhotos';

const fmt = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';

export default function ReportDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [deadline, setDeadline] = useState(15);
  const [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState(null);
  const [zoom, setZoom] = useState(false);
  const [extra, setExtra] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReport(await api.getReport(id));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // The photo is served only with the session token, so fetch it as a blob.
  const evidenceId = report?.evidence_record_id;
  useEffect(() => {
    if (!evidenceId) {
      setPhoto(null);
      return undefined;
    }
    let url;
    let cancelled = false;
    setPhoto({ loading: true });
    api
      .evidenceImage(evidenceId)
      .then(({ blob, hashMatches }) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setPhoto({ url, hashMatches });
      })
      .catch((e) => {
        if (!cancelled) setPhoto({ error: e.message });
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [evidenceId]);

  // Photos of other faces sent with the scan, e.g. the one showing the veg mark.
  useEffect(() => {
    if (!evidenceId) {
      setExtra(null);
      return undefined;
    }
    let cancelled = false;
    api
      .inspectionDetail(evidenceId)
      .then((d) => {
        if (!cancelled) setExtra({ photos: d.extra_photos || [], markPhoto: d.fssai_mark?.photo });
      })
      .catch(() => {
        if (!cancelled) setExtra(null);
      });
    return () => {
      cancelled = true;
    };
  }, [evidenceId]);

  useEffect(() => {
    if (!zoom) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setZoom(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoom]);

  const act = async (fn, successMsg) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fn();
      setNotice(successMsg(res));
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadPdf = async () => {
    setBusy(true);
    setError(null);
    try {
      const blob = await api.noticePdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `GO_notice_report_${id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadComplianceReport = async () => {
    setBusy(true);
    setError(null);
    try {
      const blob = await api.complianceReportPdf(report.evidence_record_id);
      saveBlob(blob, `FieldProof_compliance_report_scan${report.evidence_record_id}.pdf`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (loading && !report) {
    return (
      <>
        <div className="topbar"><h2>Report</h2></div>
        <div className="content"><div className="empty">Loading…</div></div>
      </>
    );
  }

  if (!report) {
    return (
      <>
        <div className="topbar"><h2>Report</h2></div>
        <div className="content"><div className="alert error">{error || 'Not found.'}</div></div>
      </>
    );
  }

  const isPending = report.status === 'pending_admin_confirmation';
  const isConfirmed = report.status === 'confirmed';
  const hasNotice = report.notice_generated;

  return (
    <>
      <div className="topbar">
        <button className="btn-ghost" onClick={() => navigate('/queue')}>← Queue</button>
        <h2>{report.report_number}</h2>
        <span className={`badge ${report.severity}`}>{report.severity}</span>
        <span className={`badge ${report.status}`}>{report.status.replaceAll('_', ' ')}</span>
        <div className="spacer" />
        {report.evidence_record_id != null && (
          <button className="btn-ghost" onClick={downloadComplianceReport} disabled={busy}>
            Compliance report (PDF)
          </button>
        )}
        {hasNotice && (
          <button className="btn-primary" onClick={downloadPdf} disabled={busy}>
            Download GO Notice
          </button>
        )}
      </div>

      <div className="content">
        {error && <div className="alert error">{error}</div>}
        {notice && <div className="alert ok">{notice}</div>}

        <div className="two-col">
          {/* ── Left: the case ─────────────────────────────────── */}
          <div>
            <div className="card">
              <h3>Contraventions cited ({report.violated_rules?.length || 0})</h3>
              {report.violated_rules?.length ? (
                <div style={{ overflowX: 'auto' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Rule</th>
                        <th>Finding</th>
                        <th>Statutory provision</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.violated_rules.map((v, i) => (
                        <tr key={`${v.rule_code}-${i}`}>
                          <td>
                            {/* A registry mismatch has no check number: the
                                inspector confirmed it on the pack (Rule 6(3)). */}
                            <strong>{v.rule_number ?? 'Registry'}</strong>
                            <div className="muted">
                              {v.source === 'registry' ? 'checked on the pack' : v.rule_code}
                            </div>
                          </td>
                          <td>
                            <div>{v.rule_name}</div>
                            {v.failure_reason && (
                              <div className="muted" style={{ marginTop: 3 }}>
                                {v.failure_reason}
                              </div>
                            )}
                            {(v.detected_value || v.required_value) && (
                              <div className="muted mono" style={{ marginTop: 3 }}>
                                detected: {v.detected_value ?? '—'} · required:{' '}
                                {v.required_value ?? '—'}
                              </div>
                            )}
                          </td>
                          <td className="muted">{v.statutory_reference}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="muted">No rules cited.</div>
              )}
            </div>

            <div className="card">
              <h3>Inspector's summary</h3>
              <p style={{ margin: 0, lineHeight: 1.5 }}>{report.violation_summary}</p>
              {report.inspector_notes && (
                <>
                  <label>Field notes</label>
                  <p style={{ margin: 0, lineHeight: 1.5 }}>{report.inspector_notes}</p>
                </>
              )}
            </div>

            {/* ── Decision panel ──────────────────────────────── */}
            <div className="card">
              <h3>Decision</h3>

              {isPending && (
                <>
                  <div className="alert info">
                    Confirm to accept these findings, or reject to close the report.
                    A GO notice can only be issued after confirmation.
                  </div>
                  <label htmlFor="notes">Your notes (recorded on the report)</label>
                  <textarea
                    id="notes"
                    value={adminNotes}
                    onChange={(e) => setAdminNotes(e.target.value)}
                    placeholder="e.g. Findings verified against the product registry. Proceed to notice."
                  />
                  <div className="btn-row" style={{ marginTop: 12 }}>
                    <button
                      className="btn-success"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => api.confirmReport(id, adminNotes),
                          () => 'Report confirmed. You can now issue the GO notice.',
                        )
                      }
                    >
                      Confirm findings
                    </button>
                    <button
                      className="btn-danger"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => api.rejectReport(id, adminNotes),
                          () => 'Report rejected and closed.',
                        )
                      }
                    >
                      Reject
                    </button>
                  </div>
                </>
              )}

              {isConfirmed && !hasNotice && (
                <>
                  <div className="alert ok">
                    Confirmed{report.confirmed_at ? ` on ${fmt(report.confirmed_at)}` : ''}.
                    Issue the show-cause notice to the manufacturer and shop.
                  </div>
                  <label htmlFor="dl">Days to show cause</label>
                  <input
                    id="dl"
                    type="number"
                    min="1"
                    max="90"
                    value={deadline}
                    onChange={(e) => setDeadline(Number(e.target.value))}
                    style={{ maxWidth: 130 }}
                  />
                  <div className="btn-row" style={{ marginTop: 12 }}>
                    <button
                      className="btn-primary"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => api.issueNotice(id, deadline),
                          (r) => `Notice ${r.notice_number} issued.`,
                        )
                      }
                    >
                      Issue GO Notice
                    </button>
                  </div>
                </>
              )}

              {hasNotice && (
                <div className="alert ok">
                  GO notice issued. Download it above to print and dispatch.
                </div>
              )}

              {report.status === 'rejected' && (
                <div className="alert info">
                  Rejected{report.rejected_at ? ` on ${fmt(report.rejected_at)}` : ''}. No notice will be issued.
                </div>
              )}

              {report.admin_notes && (
                <>
                  <label>Recorded decision notes</label>
                  <p style={{ margin: 0 }}>{report.admin_notes}</p>
                </>
              )}
            </div>
          </div>

          {/* ── Right: evidence, parties & provenance ───────────── */}
          <div>
            <div className="card">
              <h3>Evidence photo</h3>
              <EvidencePhoto
                photo={photo ?? (report.evidence_record_id ? { loading: true } : null)}
                onOpen={() => setZoom(true)}
              />
              <ExtraPhotos
                evidenceId={evidenceId}
                photos={extra?.photos}
                markPhoto={extra?.markPhoto}
              />
            </div>

            <div className="card">
              <h3>Parties</h3>
              <dl className="kv">
                <dt>Product</dt><dd>{report.product_name || '—'}</dd>
                <dt>Manufacturer</dt><dd>{report.manufacturer_name || '—'}</dd>
                <dt>Mfr address</dt><dd>{report.manufacturer_address || '—'}</dd>
                <dt>Shop</dt><dd>{report.shop_name || '—'}</dd>
                <dt>Shop address</dt><dd>{report.shop_address || '—'}</dd>
              </dl>
            </div>

            <div className="card">
              <h3>Chain of custody</h3>
              <dl className="kv">
                <dt>Evidence</dt>
                <dd>{report.evidence_record_id ? `EV-${report.evidence_record_id}` : '—'}</dd>
                <dt>Captured</dt><dd>{fmt(report.evidence_captured_at)}</dd>
                <dt>Location</dt>
                <dd>
                  {report.gps_latitude != null
                    ? `${report.gps_latitude.toFixed(5)}, ${report.gps_longitude.toFixed(5)}`
                    : '—'}
                </dd>
                <dt>SHA-256</dt>
                <dd className="mono" style={{ wordBreak: 'break-all' }}>
                  {report.evidence_sha256 || '—'}
                </dd>
              </dl>
            </div>

            <div className="card">
              <h3>Filed by</h3>
              <dl className="kv">
                <dt>Inspector</dt><dd>{report.inspector_name || '—'}</dd>
                <dt>Badge</dt><dd>{report.inspector_badge || '—'}</dd>
                <dt>Filed</dt><dd>{fmt(report.created_at)}</dd>
                <dt>Complaint</dt>
                <dd>{report.complaint_id ? `#${report.complaint_id}` : 'Inspector-initiated'}</dd>
              </dl>
            </div>
          </div>
        </div>
      </div>

      {zoom && photo?.url && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Evidence photo, full size"
          onClick={() => setZoom(false)}
        >
          <img src={photo.url} alt="Label photo submitted as evidence, full size" />
        </div>
      )}
    </>
  );
}

/** The label photo the report rests on, checked against its capture fingerprint. */
function EvidencePhoto({ photo, onOpen }) {
  if (!photo) return <div className="photo-empty">No photo is attached to this report.</div>;
  if (photo.loading) return <div className="photo-empty">Loading photo…</div>;
  if (photo.error) return <div className="alert error">Photo unavailable: {photo.error}</div>;
  return (
    <>
      <button
        type="button"
        className="photo-frame"
        onClick={onOpen}
        aria-label="Open the evidence photo full size"
      >
        <img src={photo.url} alt="Label photo submitted as evidence" />
      </button>
      <div className="photo-meta">
        <span className={`badge ${photo.hashMatches ? 'pass' : 'fail'}`}>
          {photo.hashMatches ? 'fingerprint matches' : 'fingerprint mismatch'}
        </span>
        <span className="muted">Click to enlarge · Esc to close</span>
      </div>
      {!photo.hashMatches && (
        <div className="alert error" style={{ marginTop: 10, marginBottom: 0 }}>
          This file no longer matches the SHA-256 recorded when it was captured. Don't rely on it.
        </div>
      )}
    </>
  );
}
