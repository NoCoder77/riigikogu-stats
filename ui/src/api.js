// Relative URLs when served from backend (exe or same host); build-time env or dev default otherwise
function getApiBase() {
  if (typeof window !== "undefined" && window.location?.hostname) {
    const { hostname, port } = window.location;
    if ((hostname === "127.0.0.1" || hostname === "localhost") && port !== "5173")
      return ""; // exe or prod: API on same origin
  }
  return import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : "http://localhost:8000";
}
const API_BASE = getApiBase();
const REQUEST_TIMEOUT_MS = 30000;
async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
      signal: controller.signal
    });
  } catch (fetchErr) {
    clearTimeout(timeoutId);
    if (fetchErr.name === "AbortError") {
      throw new Error("Request timed out");
    }
    throw fetchErr;
  }
  clearTimeout(timeoutId);
  if (!response.ok) {
    const text = await response.text();
    let msg = text || `Request failed: ${response.status}`;
    try {
      const json = JSON.parse(text);
      if (json.detail != null) {
        const d = Array.isArray(json.detail)
          ? json.detail.map((e) => (e.msg != null ? e.msg : JSON.stringify(e))).join("; ")
          : String(json.detail);
        msg = d || msg;
      }
    } catch (_) {}
    const err = new Error(msg);
    err.status = response.status;
    err.rawBody = text;
    throw err;
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export function createImport(payload) {
  return request("/imports", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listImports({ limit = 50, offset = 0 } = {}) {
  return request(`/imports?limit=${limit}&offset=${offset}`);
}

export function getImportCurrent() {
  return request("/imports/current");
}

export function getImportLogs(runId, { limit = 200 } = {}) {
  return request(`/imports/${runId}/logs?limit=${limit}`);
}

export function listSessions(params = {}) {
  const search = new URLSearchParams(params);
  return request(`/sessions?${search.toString()}`);
}

export function getSession(sessionId) {
  return request(`/sessions/${encodeURIComponent(sessionId)}`);
}

export function getStats() {
  return request("/stats");
}

export function getHealth() {
  return request("/health");
}

/** Request server shutdown (exe only). No response expected once server exits. */
export function quitApp() {
  const url = `${API_BASE}/api/shutdown`;
  return fetch(url, { method: "POST" });
}

export function listVotes(params = {}) {
  const search = new URLSearchParams(params);
  return request(`/votes?${search.toString()}`);
}

export function getVote(voteId) {
  return request(`/votes/${encodeURIComponent(voteId)}`);
}

export function getVoteFactionBreakdown(voteId) {
  return request(`/votes/${encodeURIComponent(voteId)}/faction-breakdown`);
}

/** Build URL for GET /export/votes with same query params as list. Use with window.location.href to trigger CSV download. */
export function getExportVotesUrl(params = {}) {
  const search = new URLSearchParams(params);
  return `${API_BASE}/export/votes?${search.toString()}`;
}

export function listPersons(params = {}) {
  const search = new URLSearchParams(params);
  return request(`/persons?${search.toString()}`);
}

export function getPerson(personId, params = {}) {
  const search = new URLSearchParams(params);
  const qs = search.toString();
  return request(`/persons/${encodeURIComponent(personId)}${qs ? `?${qs}` : ""}`);
}

export function listFactions(params = {}) {
  const search = new URLSearchParams(params);
  return request(`/factions?${search.toString()}`);
}

export function getFaction(factionId, params = {}) {
  const search = new URLSearchParams(params);
  const qs = search.toString();
  return request(`/factions/${encodeURIComponent(factionId)}${qs ? `?${qs}` : ""}`);
}
