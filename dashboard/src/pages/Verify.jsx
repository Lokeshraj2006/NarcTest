import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import { PRESUMPTIVE, RESULT_TEXT, fmt, shortHash } from './common';

const CHECKS = [
  ['image_hash', 'Photo is the same as when it was taken'],
  ['record_hash', 'Test details were not changed'],
  ['signature', 'Digital signature is valid'],
  ['chain', 'Record is correctly linked to the one before it'],
  ['fields_match', 'Saved result matches the signed result'],
];

/** Public page, no login needed. Anyone scanning the QR code lands here. */
export default function Verify() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .verify(id)
      .then(setData)
      .catch((e) =>
        setError(e.status === 404 ? `No test record with number ${id}.` : e.message),
      );
  }, [id]);

  const rec = data?.record || {};

  return (
    <div className="verify-wrap">
      <div className="verify-card">
        <div className="verify-brand">
          <strong>FieldProof</strong> - Record check
        </div>

        {!data && !error && <div className="empty">Checking record #{id}...</div>}
        {error && <div className="alert error">{error}</div>}

        {data && (
          <>
            <div className={`verify-banner ${data.ok ? 'good' : 'bad'}`}>
              <div className="big">{data.ok ? 'Record is genuine' : 'TAMPERED'}</div>
              <div>
                {data.message ||
                  (data.ok
                    ? 'Photo and details were not changed.'
                    : 'Something in this record was changed after it was saved.')}
              </div>
            </div>

            <h3>What we checked</h3>
            <ul className="checks">
              {CHECKS.map(([key, text]) => {
                const ok = data.checks?.[key];
                return (
                  <li key={key} className={ok ? 'pass' : 'fail'}>
                    <span className="tick">{ok ? '✔' : '✘'}</span> {text}
                  </li>
                );
              })}
            </ul>

            <h3>Test details</h3>
            <dl className="kv">
              <dt>Test number</dt>
              <dd>{data.test_id}</dd>
              <dt>Result</dt>
              <dd>
                <span className={`badge ${String(rec.result).toLowerCase()}`}>
                  {RESULT_TEXT[rec.result] || rec.result}
                </span>{' '}
                {rec.outcome_label}
                {rec.confidence != null && ` (${rec.confidence}% sure)`}
              </dd>
              <dt>Time</dt>
              <dd>
                {fmt(rec.created_at)}{' '}
                <span className="muted">
                  ({rec.time_source === 'ntp' ? 'internet time' : 'server clock'})
                </span>
              </dd>
              <dt>Place (GPS)</dt>
              <dd>
                {rec.latitude != null
                  ? `${Number(rec.latitude).toFixed(5)}, ${Number(rec.longitude).toFixed(5)}`
                  : '-'}
              </dd>
              <dt>Officer</dt>
              <dd>{rec.officer_name || '-'}</dd>
              <dt>Kit</dt>
              <dd>
                {rec.kit_name} {rec.kit_version != null && <span className="muted">(v{rec.kit_version})</span>}
              </dd>
              <dt>Photo fingerprint</dt>
              <dd className="mono">{shortHash(rec.image_sha256)}</dd>
              <dt>Record fingerprint</dt>
              <dd className="mono">{shortHash(rec.record_hash)}</dd>
            </dl>
          </>
        )}
        <p className="muted" style={{ marginTop: 18 }}>{PRESUMPTIVE}</p>
      </div>
    </div>
  );
}
