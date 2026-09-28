import { useEffect, useState } from 'react';
import { api } from './api';

const markWords = { vegetarian: 'veg mark', non_vegetarian: 'non-veg mark', not_found: 'no mark found' };

/**
 * Photos of other faces of the pack sent with a scan ("Scan another part").
 * Each is checked against its own capture fingerprint, like the evidence photo.
 */
export default function ExtraPhotos({ evidenceId, photos, markPhoto }) {
  const [loaded, setLoaded] = useState({});
  const [zoom, setZoom] = useState(null);

  useEffect(() => {
    if (!evidenceId || !photos?.length) return undefined;
    let cancelled = false;
    const urls = [];
    setLoaded({});
    photos.forEach((p) => {
      api
        .extraImage(evidenceId, p.index)
        .then(({ blob, hashMatches }) => {
          if (cancelled) return;
          const url = URL.createObjectURL(blob);
          urls.push(url);
          setLoaded((prev) => ({ ...prev, [p.index]: { url, hashMatches } }));
        })
        .catch((e) => {
          if (!cancelled) setLoaded((prev) => ({ ...prev, [p.index]: { error: e.message } }));
        });
    });
    return () => {
      cancelled = true;
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [evidenceId, photos]);

  useEffect(() => {
    if (!zoom) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setZoom(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoom]);

  if (!photos?.length) return null;
  return (
    <div className="extra-photos-block">
      <div className="muted" style={{ marginBottom: 6 }}>
        Other parts of the pack ({photos.length}), sent with the scan and checked for the FSSAI veg mark
      </div>
      <div className="extra-photos">
        {photos.map((p) => {
          const shot = loaded[p.index];
          return (
            <figure key={p.index}>
              {!shot ? (
                <div className="photo-empty">Loading…</div>
              ) : shot.error ? (
                <div className="photo-empty">Unavailable</div>
              ) : (
                <button
                  type="button"
                  className="photo-frame"
                  onClick={() => setZoom(shot.url)}
                  aria-label={`Open extra photo ${p.index} full size`}
                >
                  <img src={shot.url} alt={`Extra photo ${p.index} of the pack`} />
                </button>
              )}
              <figcaption>
                Extra photo {p.index}
                {markPhoto === p.index ? ' · veg mark read here' : ` · ${markWords[p.fssai_mark_status] || '—'}`}
                {shot && !shot.error && (
                  <span className={`badge ${shot.hashMatches ? 'pass' : 'fail'}`}>
                    {shot.hashMatches ? 'fingerprint matches' : 'fingerprint mismatch'}
                  </span>
                )}
              </figcaption>
            </figure>
          );
        })}
      </div>
      {zoom && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Extra photo, full size"
          onClick={() => setZoom(null)}
        >
          <img src={zoom} alt="Extra photo of the pack, full size" />
        </div>
      )}
    </div>
  );
}
