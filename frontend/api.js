// Thin fetch wrapper for the Oroscope API: adds the Cognito token, retries while the database
// wakes up (503), and turns FastAPI error bodies into readable messages.
(function () {
  "use strict";
  const cfg = window.OROSCOPE_CONFIG;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  class ApiError extends Error {
    constructor(status, message) { super(message); this.status = status; }
  }

  function detailText(data, status) {
    if (data && typeof data.detail === "string") return data.detail;
    if (data && Array.isArray(data.detail)) {
      return data.detail.map((d) => (d.loc ? d.loc.slice(1).join(".") + ": " : "") + d.msg).join("; ");
    }
    if (status === 401) return "Session expired. Please log in again.";
    return "Request failed (" + status + ").";
  }

  async function request(method, path, body, onWaiting) {
    const token = await window.OroscopeAuth.getIdToken();
    for (let attempt = 0; attempt < 8; attempt++) {
      let res;
      try {
        res = await fetch(cfg.apiUrl + path, {
          method,
          headers: Object.assign({ Authorization: "Bearer " + token }, body ? { "Content-Type": "application/json" } : {}),
          body: body ? JSON.stringify(body) : undefined,
        });
      } catch (_) {
        // fetch only throws when the request never got a response (offline, DNS, blocked)
        throw new ApiError(0, "Cannot reach the server. Check your internet connection and try again.");
      }
      // 503 = Aurora is resuming from auto-pause (scale-to-zero). Retry-After is not readable
      // cross-origin, so wait a fixed few seconds.
      if (res.status === 503) {
        if (onWaiting) onWaiting();
        await sleep(6000);
        continue;
      }
      let data = null;
      try { data = await res.json(); } catch (_) { /* empty or non-JSON body */ }
      if (!res.ok) throw new ApiError(res.status, detailText(data, res.status));
      return data;
    }
    throw new ApiError(503, "The database is still starting. Please try again in a minute.");
  }

  window.OroscopeApi = {
    ApiError,
    get: (p, w) => request("GET", p, null, w),
    post: (p, b, w) => request("POST", p, b === undefined ? null : b, w),
    patch: (p, b, w) => request("PATCH", p, b, w),
  };
})();
