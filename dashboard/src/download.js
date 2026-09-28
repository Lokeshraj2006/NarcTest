/** Save a Blob (a PDF or a CSV) from the browser. */
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const cell = (value) => {
  const text = value == null ? '' : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};

/**
 * Save rows as a CSV that Excel opens directly — the editable format the
 * problem statement asks for. `columns` is [[heading, row => value], ...].
 * The byte-order mark makes Excel read ₹ and other non-ASCII text as UTF-8.
 */
export function saveCsv(rows, columns, filename) {
  const lines = [
    columns.map(([heading]) => cell(heading)).join(','),
    ...rows.map((row) => columns.map(([, get]) => cell(get(row))).join(',')),
  ];
  saveBlob(new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }), filename);
}

export const stamp = () => new Date().toISOString().slice(0, 10);
