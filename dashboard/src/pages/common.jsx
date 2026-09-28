export const fmt = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '-';

export const RESULT_COLORS = {
  POSITIVE: '#dc2626',
  NEGATIVE: '#16a34a',
  INCONCLUSIVE: '#7c3aed',
};

export const RESULT_TEXT = {
  POSITIVE: 'POSITIVE',
  NEGATIVE: 'NEGATIVE',
  INCONCLUSIVE: 'NOT SURE',
};

export function ResultBadge({ result }) {
  const r = String(result || '').toUpperCase();
  return <span className={`badge ${r.toLowerCase()}`}>{RESULT_TEXT[r] || r || '-'}</span>;
}

export function ColourChip({ rgb, size = 18, title }) {
  if (!Array.isArray(rgb) || rgb.length < 3) return <span className="muted">-</span>;
  const [r, g, b] = rgb.map((v) => Math.max(0, Math.min(255, Math.round(Number(v) || 0))));
  return (
    <span
      className="chip"
      title={title || `rgb(${r}, ${g}, ${b})`}
      style={{ width: size, height: size, background: `rgb(${r}, ${g}, ${b})` }}
    />
  );
}

export const shortHash = (h) => (h ? `${h.slice(0, 10)}...${h.slice(-6)}` : '-');

export const PRESUMPTIVE =
  'Presumptive field result - not a substitute for laboratory confirmatory testing.';
