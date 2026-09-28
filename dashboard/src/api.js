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
      `Cannot reach the backend at ${BASE}. Is the backend running?`,
      0,
    );
  }

  if (res.status === 401) {
    clearSession();
    throw new ApiError('Your login has expired. Please sign in again.', 401);
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

const withHash = async (res) => ({
  blob: await res.blob(),
  hashMatches: res.headers.get('X-Evidence-Sha256-Match') === 'true',
});

// Lists may come back as a plain array or wrapped as {rows}/{items}.
export const asList = (x) =>
  Array.isArray(x) ? x : x?.rows || x?.items || x?.tests || x?.kits || [];

export const api = {
  login: (usernameOrEmail, password) =>
    request('/auth/login', {
      method: 'POST',
      body: { username_or_email: usernameOrEmail, password },
    }),
  health: () => request('/health'),

  // tests
  listTests: (filters) => request('/tests', { params: filters }).then(asList),
  getTest: (id) => request(`/tests/${id}`),
  testImage: async (id) =>
    withHash(await request(`/tests/${id}/image`, { accept: 'image/*', rawResponse: true })),
  testPdf: (id) => request(`/tests/${id}/pdf`, { raw: true }),
  exportCsv: (filters) =>
    request('/tests/export.csv', { params: filters, accept: 'text/csv', rawResponse: true }).then(
      (r) => r.blob(),
    ),

  // review
  pendingReviews: () => request('/reviews/pending').then(asList),
  reviewTest: (id, decision, note) =>
    request(`/tests/${id}/review`, { method: 'POST', body: { decision, note: note || '' } }),

  // kits
  listKits: () => request('/kits').then(asList),
  listAllKits: () => request('/kits/all').then(asList),
  updateKit: (id, kit) => request(`/kits/${id}`, { method: 'PUT', body: kit }),
  setKitActive: (id, isActive) =>
    request(`/kits/${id}/active`, { method: 'PATCH', body: { is_active: isActive } }),

  // public
  verify: (id) => request(`/verify/${id}`),
};

export const API_BASE = BASE;
