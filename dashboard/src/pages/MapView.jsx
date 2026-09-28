import L from 'leaflet';
import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

// Pin colours mirror the mobile app so the two surfaces read identically.
const COLORS = {
  darkred: '#7f1d1d',
  red: '#dc2626',
  orange: '#ea580c',
  yellow: '#ca8a04',
  grey: '#6b7280',
  green: '#15803d',
  amber: '#b45309',
  complaint: '#f59e0b',
};

const BENGALURU = [12.9716, 77.5946];

/** Fits the viewport to all plotted points whenever they change. */
function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    if (points.length === 1) {
      map.setView(points[0], 15);
    } else {
      map.fitBounds(L.latLngBounds(points), { padding: [50, 50], maxZoom: 16 });
    }
  }, [points, map]);
  return null;
}

export default function MapView() {
  const [reports, setReports] = useState([]);
  const [scans, setScans] = useState([]);
  const [complaints, setComplaints] = useState([]);
  const [layers, setLayers] = useState({ reports: true, scans: true, complaints: true });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const [r, s, c] = await Promise.all([
          api.listReports(),
          api.inspectionLog(),
          api.pendingComplaints(),
        ]);
        setReports((r.rows || []).filter((x) => x.gps_latitude != null));
        setScans((s.rows || []).filter((x) => x.gps_latitude != null));
        setComplaints((c.rows || []).filter((x) => x.gps_latitude != null));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const points = useMemo(() => {
    const p = [];
    if (layers.reports) reports.forEach((r) => p.push([r.gps_latitude, r.gps_longitude]));
    if (layers.scans) scans.forEach((r) => p.push([r.gps_latitude, r.gps_longitude]));
    if (layers.complaints) complaints.forEach((r) => p.push([r.gps_latitude, r.gps_longitude]));
    return p;
  }, [layers, reports, scans, complaints]);

  const toggle = (k) => setLayers((l) => ({ ...l, [k]: !l[k] }));

  return (
    <>
      <div className="topbar">
        <h2>Enforcement Map</h2>
        <div className="spacer" />
        <div className="btn-row">
          <button className={layers.reports ? 'btn-primary' : 'btn-ghost'} onClick={() => toggle('reports')}>
            Reports ({reports.length})
          </button>
          <button className={layers.scans ? 'btn-primary' : 'btn-ghost'} onClick={() => toggle('scans')}>
            Scans ({scans.length})
          </button>
          <button className={layers.complaints ? 'btn-primary' : 'btn-ghost'} onClick={() => toggle('complaints')}>
            Complaints ({complaints.length})
          </button>
        </div>
      </div>

      <div className="content">
        {error && <div className="alert error">{error}</div>}
        {!error && !loading && points.length === 0 && (
          <div className="alert info">
            Nothing to plot yet — records appear here once scans carry GPS coordinates.
          </div>
        )}

        <div className="map-holder">
          <MapContainer center={BENGALURU} zoom={11} scrollWheelZoom>
            <TileLayer
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              maxZoom={19}
            />
            <FitBounds points={points} />

            {layers.reports &&
              reports.map((r) => (
                <CircleMarker
                  key={`vr-${r.id}`}
                  center={[r.gps_latitude, r.gps_longitude]}
                  radius={11}
                  pathOptions={{
                    color: '#fff',
                    weight: 2,
                    fillColor: COLORS[r.pin_color] || COLORS.red,
                    fillOpacity: 0.95,
                  }}
                >
                  <Popup>
                    <strong>{r.report_number}</strong>
                    <br />
                    {r.product_name || 'Unknown product'}
                    <br />
                    <span className="muted">
                      {r.severity} · {r.violated_rule_count} rule(s) · {r.status.replaceAll('_', ' ')}
                    </span>
                    <br />
                    {r.shop_name && <em>{r.shop_name}</em>}
                    <br />
                    <button
                      className="btn-primary"
                      style={{ marginTop: 6, padding: '4px 10px' }}
                      onClick={() => navigate(`/reports/${r.id}`)}
                    >
                      Open report
                    </button>
                  </Popup>
                </CircleMarker>
              ))}

            {layers.scans &&
              scans.map((r) => (
                <CircleMarker
                  key={`ev-${r.evidence_record_id}`}
                  center={[r.gps_latitude, r.gps_longitude]}
                  radius={7}
                  pathOptions={{
                    color: '#fff',
                    weight: 1.5,
                    fillColor: COLORS[r.pin_color] || COLORS.green,
                    fillOpacity: 0.85,
                  }}
                >
                  <Popup>
                    <strong>{r.product_name || `Evidence #${r.evidence_record_id}`}</strong>
                    <br />
                    {r.overall_status.replaceAll('_', ' ')}
                    <br />
                    <span className="muted">{new Date(r.timestamp).toLocaleString()}</span>
                    {r.action_reason && (
                      <>
                        <br />
                        <span className="muted">{r.action_reason.slice(0, 120)}</span>
                      </>
                    )}
                  </Popup>
                </CircleMarker>
              ))}

            {layers.complaints &&
              complaints.map((r) => (
                <CircleMarker
                  key={`cm-${r.complaint_id}`}
                  center={[r.gps_latitude, r.gps_longitude]}
                  radius={9}
                  pathOptions={{
                    color: '#fff',
                    weight: 2,
                    fillColor: COLORS.complaint,
                    fillOpacity: 0.9,
                  }}
                >
                  <Popup>
                    <strong>Consumer report</strong>
                    <br />
                    {r.product_name || 'Unknown product'}
                    <br />
                    <span className="muted">
                      Awaiting inspector · {new Date(r.filed_at).toLocaleDateString()}
                    </span>
                  </Popup>
                </CircleMarker>
              ))}
          </MapContainer>
        </div>

        <div className="legend">
          <span><i className="dot" style={{ background: COLORS.darkred }} /> Critical report</span>
          <span><i className="dot" style={{ background: COLORS.red }} /> Major / action needed</span>
          <span><i className="dot" style={{ background: COLORS.orange }} /> Moderate</span>
          <span><i className="dot" style={{ background: COLORS.complaint }} /> Consumer complaint</span>
          <span><i className="dot" style={{ background: COLORS.green }} /> Compliant scan</span>
          <span><i className="dot" style={{ background: COLORS.grey }} /> Resolved</span>
        </div>
      </div>
    </>
  );
}
