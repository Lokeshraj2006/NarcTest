import L from 'leaflet';
import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { RESULT_COLORS, RESULT_TEXT, fmt } from './common';

const START_CENTRE = [12.9716, 77.5946];

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    if (points.length === 1) map.setView(points[0], 15);
    else map.fitBounds(L.latLngBounds(points), { padding: [50, 50], maxZoom: 16 });
  }, [points, map]);
  return null;
}

export default function TestMap() {
  const [tests, setTests] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listTests({})
      .then((rows) => setTests(rows.filter((t) => t.latitude != null && t.longitude != null)))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const points = useMemo(() => tests.map((t) => [t.latitude, t.longitude]), [tests]);

  return (
    <>
      <div className="topbar">
        <h2>Test Map</h2>
        <div className="spacer" />
        <span className="muted">{tests.length} tests with GPS</span>
      </div>
      <div className="content">
        {error && <div className="alert error">{error}</div>}
        {!error && !loading && tests.length === 0 && (
          <div className="alert info">
            No tests with GPS yet. They will show up here once officers do tests.
          </div>
        )}
        <div className="map-holder">
          <MapContainer center={START_CENTRE} zoom={11} scrollWheelZoom>
            <TileLayer
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              maxZoom={19}
            />
            <FitBounds points={points} />
            {tests.map((t) => (
              <CircleMarker
                key={t.id}
                center={[t.latitude, t.longitude]}
                radius={10}
                pathOptions={{
                  color: '#fff',
                  weight: 2,
                  fillColor: RESULT_COLORS[t.result] || '#6b7280',
                  fillOpacity: 0.92,
                }}
              >
                <Popup>
                  <strong style={{ color: RESULT_COLORS[t.result] }}>
                    {RESULT_TEXT[t.result] || t.result}
                  </strong>
                  {t.outcome_label && <> - {t.outcome_label}</>}
                  <br />
                  <span className="muted">{fmt(t.created_at)}</span>
                  <br />
                  {t.officer_name && (
                    <>
                      Officer: {t.officer_name}
                      <br />
                    </>
                  )}
                  Test #{t.id} - <Link to={`/tests/${t.id}`}>Open</Link>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
        <div className="legend">
          <span><i className="dot" style={{ background: RESULT_COLORS.POSITIVE }} /> Positive</span>
          <span><i className="dot" style={{ background: RESULT_COLORS.NEGATIVE }} /> Negative</span>
          <span><i className="dot" style={{ background: RESULT_COLORS.INCONCLUSIVE }} /> Not sure</span>
        </div>
      </div>
    </>
  );
}
