/* Thin wrapper around fetch() for the backend API. */
const API = (() => {
  const KEY = "inv_token";
  let token = null;
  try { token = localStorage.getItem(KEY); } catch (e) { /* storage blocked */ }
  let unauthorizedHandler = () => {};

  class ApiError extends Error {
    constructor(message, status, details) {
      super(message);
      this.status = status;
      this.details = details || {};
    }
  }

  async function request(method, path, { params, body } = {}) {
    let url = "/api" + path;
    if (params) {
      const qs = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") qs.append(k, v);
      });
      const s = qs.toString();
      if (s) url += "?" + s;
    }
    let res;
    try {
      res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new ApiError("Cannot reach the server. Is the backend running?", 0);
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      if (res.status === 401 && path !== "/auth/login") unauthorizedHandler();
      throw new ApiError((data && data.error) || `Request failed (${res.status})`, res.status, data && data.details);
    }
    return data;
  }

  return {
    ApiError,
    hasToken: () => !!token,
    setToken(t) {
      token = t;
      try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    },
    onUnauthorized(fn) { unauthorizedHandler = fn; },
    get: (path, params) => request("GET", path, { params }),
    post: (path, body) => request("POST", path, { body: body || {} }),
    put: (path, body) => request("PUT", path, { body: body || {} }),
    del: (path) => request("DELETE", path),
  };
})();
