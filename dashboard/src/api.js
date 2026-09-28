/**
 * FieldProof API client.
 *
 * Base URL comes from VITE_API_BASE at build/dev time, defaulting to the
 * local backend. The JWT is kept in sessionStorage so closing the tab ends
 * the session — appropriate for a shared enforcement workstation.
 */

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const TOKEN_KEY = 'fieldproof_token';
const USER_KEY = 'fieldproof_user';

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t) => sessionStorage.setItem(TOKEN_KEY, t);
export const clearSession = () => {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
};

export const getUser = () => {
  try {
    return JSON.parse(sessionStorage.getItem(USER_KEY) || 'null');
  } catch {
    return null;
  }
};
export const setUser = (u) => sessionStorage.setItem(USER_KEY, JSON.stringify(u));

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(
  path,
  { method = 'GET', body, params, raw = false, accept, rawResponse = false } = {},
) {
  const url = new URL(BASE + path);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
    });
  }

  const headers = { Accept: accept || (raw ? 'application/pdf' : 'application/json') };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let res;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${BASE}. Is it running?`,
      0,
    );
  }

  if (res.status === 401) {
    clearSession();
    throw new ApiError('Session expired — please sign in again.', 401);
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j.detail === 'string') detail = j.detail;
      else if (Array.isArray(j.detail)) detail = j.detail.map((d) => d.msg).join('; ');
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }

  if (rawResponse) return res;
  if (raw) return res.blob();
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // ── auth ───────────────────────────────────────────────────────────
  login: (usernameOrEmail, password) =>
    request('/auth/login', {
      method: 'POST',
      body: { username_or_email: usernameOrEmail, password },
    }),

  health: () => request('/health'),

  // ── violation queue (the admin's core workflow) ────────────────────
  listReports: (status) => request('/violations', { params: { status, limit: 500 } }),
  getReport: (id) => request(`/violations/${id}`),
  confirmReport: (id, adminNotes) =>
    request(`/violations/${id}/confirm`, {
      method: 'POST',
      body: { admin_notes: adminNotes || null },
    }),
  rejectReport: (id, adminNotes) =>
    request(`/violations/${id}/reject`, {
      method: 'POST',
      body: { admin_notes: adminNotes || null },
    }),
  issueNotice: (id, days = 15) =>
    request(`/violations/${id}/notice`, {
      method: 'POST',
      params: { response_deadline_days: days },
    }),
  noticePdf: (id) => request(`/violations/${id}/notice.pdf`, { raw: true }),
  // The compliance report of one scan (the inspection report, not the notice).
  complianceReportPdf: (evidenceId) =>
    request(`/legal-notice/${evidenceId}/generate`, { raw: true }),

  // ── rule catalogue ─────────────────────────────────────────────────
  listRules: () => request('/rules'),
  updateRule: (id, patch) => request(`/rules/${id}`, { method: 'PATCH', body: patch }),

  // ── system-wide view ───────────────────────────────────────────────
  inspectionLog: (onlyActionNeeded = false) =>
    request('/inspections/log', {
      params: { limit: 500, only_action_needed: onlyActionNeeded },
    }),
  inspectionDetail: (evidenceId) => request(`/inspections/${evidenceId}`),
  // The label photo, and whether it still matches the SHA-256 recorded at capture.
  evidenceImage: async (evidenceId) => {
    const res = await request(`/inspections/${evidenceId}/image`, {
      accept: 'image/*',
      rawResponse: true,
    });
    return {
      blob: await res.blob(),
      hashMatches: res.headers.get('X-Evidence-Sha256-Match') === 'true',
    };
  },
  // A photo of another face of the pack sent with the scan, same fingerprint check.
  extraImage: async (evidenceId, index) => {
    const res = await request(`/inspections/${evidenceId}/extra-image/${index}`, {
      accept: 'image/*',
      rawResponse: true,
    });
    return {
      blob: await res.blob(),
      hashMatches: res.headers.get('X-Evidence-Sha256-Match') === 'true',
    };
  },
  pendingComplaints: () => request('/complaints/pending', { params: { limit: 500 } }),
};

export const API_BASE = BASE;
