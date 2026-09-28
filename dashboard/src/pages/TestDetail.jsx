import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import { saveBlob } from '../download';
import { ColourChip, PRESUMPTIVE, ResultBadge, fmt, shortHash } from './common';

/** Photo + fingerprint badge + record fields + PDF + verify link for one test. */
export function TestDetailPanel({ testId, onClose }) {
  const [test, setTest] = useState(null);
  const [error, setError] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setTest(null);
    setError(null);
    api
      .getTest(testId)
      .then((t) => !cancelled && setTest(t))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [testId]);

  // The photo needs the login token, so fetch it as a blob.
  useEffect(() => {
    let url;
    let cancelled = false;
    setPhoto({ loading: true });
    api
      .testImage(testId)
      .then(({ blob, hashMatches }) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setPhoto({ url, hashMatches });
      })
      .catch((e) => !cancelled && setPhoto({ error: e.message }));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [testId]);

  const downloadPdf = async () => {
    setBusy(true);
    try {
      saveBlob(await api.testPdf(testId), `fieldproof-test-${testId}.pdf`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const verifyHref = `/verify/${testId}`;

  return (
    <div className="card detail-panel">
      <div className="panel-head">
        <h3>Test #{testId}</h3>
        {test && <ResultBadge result={test.result} />}
        <div className="spacer" />
        {onClose && (
          <button className="btn-ghost" onClick={onClose}>
            Close
          </button>
        )}
      </div>

      {error && <div className="alert error">{error}</div>}

      {photo?.loading && <div className="photo-empty">Loading photo...</div>}
      {photo?.error && <div className="photo-empty">Could not load photo: {photo.error}</div>}
      {photo?.url && (
        <>
          <a className="photo-frame" href={photo.url} target="_blank" rel="noreferrer">
            <img src={photo.url} alt={`Test ${testId} photo`} />
          </a>
          <div className="photo-meta">
            {photo.hashMatches ? (
              <span className="badge negative">Photo matches its fingerprint</span>
            ) : (
              <span className="badge positive">Photo CHANGED</span>
            )}
          </div>
        </>
      )}

      {test && (
        <>
          <div className={`result-banner ${String(test.result).toLowerCase()}`}>
            <div className="big">{test.result === 'INCONCLUSIVE' ? 'NOT SURE' : test.result}</div>
            <div>{test.outcome_label || test.reason || ''}</div>
            {test.confidence != null && <div className="small">{test.confidence}% sure</div>}
          </div>

          <dl className="kv">
            <dt>Test ID</dt>
            <dd className="mono">{test.test_uid}</dd>
            <dt>Time</dt>
            <dd>
              {fmt(test.ntp_time || test.created_at)}{' '}
              <span className="muted">({({ ntp: 'internet time (NTP)', https: 'internet time (HTTPS)' })[test.time_source] || 'server clock'})</span>
            </dd>
            <dt>Officer</dt>
            <dd>{test.officer_name || test.officer_id}</dd>
            <dt>Kit</dt>
            <dd>
              {test.kit_name} <span className="muted">(v{test.kit_version})</span>
            </dd>
            <dt>Why not sure</dt>
            <dd>{test.reason || '-'}</dd>
            <dt>Colour seen</dt>
            <dd className="chips">
              <ColourChip rgb={test.measured_rgb} size={22} title="Measured colour" />
              <span className="muted">vs kit colours:</span>
              {(test.kit_outcomes || []).map((o) => (
                <ColourChip key={o.label} rgb={o.srgb} title={`${o.label} (${o.category})`} />
              ))}
            </dd>
            <dt>GPS</dt>
            <dd>
              {test.latitude != null ? `${Number(test.latitude).toFixed(5)}, ${Number(test.longitude).toFixed(5)}` : '-'}
              {test.gps_accuracy_m != null && <span className="muted"> (+/- {Math.round(test.gps_accuracy_m)} m)</span>}
              {test.gps_is_mock && <span className="badge positive" style={{ marginLeft: 6 }}>Fake GPS</span>}
            </dd>
            <dt>Photo hash</dt>
            <dd className="mono">{shortHash(test.image_sha256)}</dd>
            <dt>Record hash</dt>
            <dd className="mono">{shortHash(test.record_hash)}</dd>
            <dt>Previous hash</dt>
            <dd className="mono">{test.prev_record_hash === 'GENESIS' ? 'GENESIS (first record)' : shortHash(test.prev_record_hash)}</dd>
            <dt>Signed</dt>
            <dd>{test.signature ? `Yes (${test.key_id})` : 'No'}</dd>
            <dt>Review</dt>
            <dd>{test.review_status || '-'}</dd>
          </dl>

          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn-primary" onClick={downloadPdf} disabled={busy}>
              {busy ? 'Making PDF...' : 'Download PDF'}
            </button>
            <a className="btn-ghost btn-link" href={verifyHref} target="_blank" rel="noreferrer">
              Open verify page
            </a>
          </div>
          <p className="muted" style={{ marginTop: 12 }}>{PRESUMPTIVE}</p>
        </>
      )}
    </div>
  );
}

export default function TestDetail() {
  const { id } = useParams();
  return (
    <>
      <div className="topbar">
        <Link to="/tests">&larr; Back to Test Log</Link>
      </div>
      <div className="content" style={{ maxWidth: 760 }}>
        <TestDetailPanel testId={id} />
      </div>
    </>
  );
}
