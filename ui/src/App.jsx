import React, { useEffect, useRef, useState } from "react";
import {
  createImport,
  getExportVotesUrl,
  getFaction,
  getHealth,
  getImportCurrent,
  getImportLogs,
  getPerson,
  getSession,
  getStats,
  getVote,
  listFactions,
  listImports,
  listPersons,
  listSessions,
  listVotes,
  quitApp
} from "./api.js";

const defaultRange = {
  startDate: "2013-01-01",
  endDate: "2013-01-07",
  stepDays: 7,
  onlyVotings: false,
  onlySittings: false,
  initDb: false,
  syncUsergroups: false
};

export default function App() {
  const [importForm, setImportForm] = useState(defaultRange);
  const [importHistory, setImportHistory] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [sessionTotal, setSessionTotal] = useState(null);
  const [votes, setVotes] = useState([]);
  const [voteTotal, setVoteTotal] = useState(null);
  const [sessionFilters, setSessionFilters] = useState({
    startDate: "",
    endDate: "",
    status: ""
  });
  const [sessionSort, setSessionSort] = useState({ sortBy: "session_date", order: "desc" });
  const POLICY_AREAS = ["Economic", "Social", "Foreign", "Environment", "Justice", "Other"];
  const [voteFilters, setVoteFilters] = useState({
    startDate: "",
    endDate: "",
    outcome: "",
    choice: "",
    subjectSearch: "",
    policyArea: ""
  });
  const [voteSort, setVoteSort] = useState({ sortBy: "vote_time", order: "desc" });
  const [sessionOffset, setSessionOffset] = useState(0);
  const [sessionLimit] = useState(50);
  const [voteOffset, setVoteOffset] = useState(0);
  const [voteLimit] = useState(50);
  const [statusMessage, setStatusMessage] = useState("");
  const [loadingImports, setLoadingImports] = useState(false);
  const [errorImports, setErrorImports] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [errorSessions, setErrorSessions] = useState("");
  const [loadingVotes, setLoadingVotes] = useState(false);
  const [errorVotes, setErrorVotes] = useState("");
  const [selectedVoteId, setSelectedVoteId] = useState(null);
  const [voteDetail, setVoteDetail] = useState(null);
  const [loadingVoteDetail, setLoadingVoteDetail] = useState(false);
  const [errorVoteDetail, setErrorVoteDetail] = useState("");
  const [persons, setPersons] = useState([]);
  const [personTotal, setPersonTotal] = useState(null);
  const [personOffset, setPersonOffset] = useState(0);
  const [personLimit] = useState(50);
  const [personSort, setPersonSort] = useState({ sortBy: "votes_recorded", order: "desc" });
  const [personDetail, setPersonDetail] = useState(null);
  const [selectedPersonId, setSelectedPersonId] = useState(null);
  const [personDetailVoteTypeFilter, setPersonDetailVoteTypeFilterState] = useState("");
  const [personDetailPolicyAreaFilter, setPersonDetailPolicyAreaFilterState] = useState("");
  const [loadingPersonDetail, setLoadingPersonDetail] = useState(false);
  const [errorPersonDetail, setErrorPersonDetail] = useState("");
  const [factions, setFactions] = useState([]);
  const [factionTotal, setFactionTotal] = useState(null);
  const [factionOffset, setFactionOffset] = useState(0);
  const [factionLimit] = useState(50);
  const [factionDetail, setFactionDetail] = useState(null);
  const [selectedFactionId, setSelectedFactionId] = useState(null);
  const [factionDetailPolicyAreaFilter, setFactionDetailPolicyAreaFilterState] = useState("");
  const [loadingFactionDetail, setLoadingFactionDetail] = useState(false);
  const [errorFactionDetail, setErrorFactionDetail] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [sessionDetail, setSessionDetail] = useState(null);
  const [loadingSessionDetail, setLoadingSessionDetail] = useState(false);
  const [errorSessionDetail, setErrorSessionDetail] = useState("");
  const [stats, setStats] = useState(null);
  const [importCurrentRun, setImportCurrentRun] = useState(null);
  const [importLogs, setImportLogs] = useState([]);
  const [healthInfo, setHealthInfo] = useState(null);
  const [apiReady, setApiReady] = useState(false);
  const [shuttingDown, setShuttingDown] = useState(false);
  const [reloadingData, setReloadingData] = useState(false);
  const [mainTab, setMainTab] = useState("dashboard");
  const hadRunningImportRef = useRef(false);

  async function refreshImports() {
    setLoadingImports(true);
    setErrorImports("");
    try {
      const data = await listImports();
      setImportHistory(data);
    } catch (error) {
      setErrorImports(error.message || "Failed to load imports");
    } finally {
      setLoadingImports(false);
    }
  }

  async function refreshSessions(offsetOverride) {
    const offset = offsetOverride !== undefined ? offsetOverride : sessionOffset;
    setLoadingSessions(true);
    setErrorSessions("");
    try {
      const params = {
        ...Object.fromEntries(
          Object.entries(sessionFilters).filter(([, value]) => value)
        ),
        sortBy: sessionSort.sortBy,
        order: sessionSort.order,
        limit: sessionLimit,
        offset
      };
      const data = await listSessions(params);
      setSessions(data.items ?? data);
      setSessionTotal(data.total ?? null);
      if (offsetOverride !== undefined) setSessionOffset(offset);
    } catch (error) {
      setErrorSessions(error.message || "Failed to load sessions");
    } finally {
      setLoadingSessions(false);
    }
  }

  async function refreshVotes(offsetOverride) {
    const offset = offsetOverride !== undefined ? offsetOverride : voteOffset;
    setLoadingVotes(true);
    setErrorVotes("");
    try {
      const params = {
        ...Object.fromEntries(
          Object.entries(voteFilters).filter(
            ([key, value]) =>
              value != null &&
              value !== "" &&
              key !== "subjectSearch" &&
              key !== "policyArea"
          )
        ),
        sortBy: voteSort.sortBy,
        order: voteSort.order,
        limit: voteLimit,
        offset
      };
      if (voteFilters.subjectSearch) params.subjectContains = voteFilters.subjectSearch;
      if (voteFilters.policyArea) params.policyArea = voteFilters.policyArea;
      const data = await listVotes(params);
      setVotes(data.items ?? data);
      setVoteTotal(data.total ?? null);
      if (offsetOverride !== undefined) setVoteOffset(offset);
    } catch (error) {
      setErrorVotes(error.message || "Failed to load votes");
    } finally {
      setLoadingVotes(false);
    }
  }

  async function refreshPersons(offsetOverride) {
    const offset = offsetOverride !== undefined ? offsetOverride : personOffset;
    try {
      const params = {
        sortBy: personSort.sortBy,
        order: personSort.order,
        limit: personLimit,
        offset
      };
      const data = await listPersons(params);
      setPersons(data.items ?? data);
      setPersonTotal(data.total ?? null);
      if (offsetOverride !== undefined) setPersonOffset(offset);
    } catch (_) {
      setPersons([]);
      setPersonTotal(null);
    }
  }

  async function refreshFactions(offsetOverride) {
    const offset = offsetOverride !== undefined ? offsetOverride : factionOffset;
    try {
      const data = await listFactions({ limit: factionLimit, offset });
      setFactions(data.items ?? data);
      setFactionTotal(data.total ?? null);
      if (offsetOverride !== undefined) setFactionOffset(offset);
    } catch (_) {
      setFactions([]);
      setFactionTotal(null);
    }
  }

  /** Retry an async function a few times with delay (for initial load when server may not be ready yet). */
  async function withRetry(fn, retries = 2, delayMs = 500) {
    let lastErr;
    for (let i = 0; i <= retries; i++) {
      try {
        return await fn();
      } catch (e) {
        lastErr = e;
        if (i < retries) await new Promise((r) => setTimeout(r, delayMs));
      }
    }
    throw lastErr;
  }

  async function refreshStats() {
    try {
      const data = await getStats();
      setStats(data);
    } catch (_) {
      setStats(null);
    }
  }

  useEffect(() => {
    // Initial load: only stats and imports so dashboard stays fast; analytics load on demand
    const load = async () => {
      try {
        const data = await withRetry(getStats, 2, 500);
        setStats(data);
      } catch (_) {
        setStats(null);
      }
      try {
        await withRetry(refreshImports, 2, 500);
      } catch (_) {}
    };
    load();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      while (!cancelled) {
        try {
          const data = await getHealth();
          if (!cancelled) {
            setHealthInfo(data);
            if (data?.status === "ok") {
              setApiReady(true);
              return;
            }
          }
        } catch (_) {}
        await new Promise((r) => setTimeout(r, 1000));
      }
    };
    check();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const poll = async () => {
      try {
        const current = await getImportCurrent();
        if (current?.id != null && (current?.status === "running" || current?.status === "queued")) {
          hadRunningImportRef.current = true;
          setImportCurrentRun(current);
          const logs = await getImportLogs(current.id, { limit: 100 });
          setImportLogs(Array.isArray(logs) ? logs : []);
        } else {
          if (hadRunningImportRef.current) {
            hadRunningImportRef.current = false;
            refreshImports();
          }
          setImportCurrentRun(null);
          setImportLogs([]);
        }
      } catch (_) {
        setImportCurrentRun(null);
        setImportLogs([]);
      }
    };
    poll();
    const interval = setInterval(poll, 2500);
    return () => clearInterval(interval);
  }, []);

  function closeVoteDetail() {
    setSelectedVoteId(null);
    setVoteDetail(null);
    setErrorVoteDetail("");
  }

  function closePersonDetail() {
    setSelectedPersonId(null);
    setPersonDetail(null);
    setPersonDetailVoteTypeFilterState("");
    setPersonDetailPolicyAreaFilterState("");
    setErrorPersonDetail("");
  }

  async function openPersonDetail(personId, voteTypeFilter = "") {
    setSelectedPersonId(personId);
    setPersonDetail(null);
    setPersonDetailVoteTypeFilterState("");
    setPersonDetailPolicyAreaFilterState("");
    setErrorPersonDetail("");
    setLoadingPersonDetail(true);
    try {
      const params = {};
      if (voteTypeFilter) params.voteType = voteTypeFilter;
      const data = await getPerson(personId, params);
      setPersonDetail(data);
    } catch (error) {
      setErrorPersonDetail(error.message || "Failed to load person");
    } finally {
      setLoadingPersonDetail(false);
    }
  }

  async function refetchPersonDetailWithFilters(voteType, policyArea) {
    if (!selectedPersonId) return;
    setLoadingPersonDetail(true);
    try {
      const params = {};
      if (voteType) params.voteType = voteType;
      if (policyArea) params.policyArea = policyArea;
      const data = await getPerson(selectedPersonId, params);
      setPersonDetail(data);
    } catch (error) {
      setErrorPersonDetail(error.message || "Failed to load person");
    } finally {
      setLoadingPersonDetail(false);
    }
  }

  async function setPersonDetailVoteTypeFilter(voteType) {
    setPersonDetailVoteTypeFilterState(voteType);
    await refetchPersonDetailWithFilters(voteType, personDetailPolicyAreaFilter);
  }

  async function setPersonDetailPolicyAreaFilter(policyArea) {
    setPersonDetailPolicyAreaFilterState(policyArea);
    await refetchPersonDetailWithFilters(personDetailVoteTypeFilter, policyArea);
  }

  function closeFactionDetail() {
    setSelectedFactionId(null);
    setFactionDetail(null);
    setFactionDetailPolicyAreaFilterState("");
    setErrorFactionDetail("");
  }

  async function openFactionDetail(factionId) {
    setSelectedFactionId(factionId);
    setFactionDetail(null);
    setFactionDetailPolicyAreaFilterState("");
    setErrorFactionDetail("");
    setLoadingFactionDetail(true);
    try {
      const data = await getFaction(factionId);
      setFactionDetail(data);
    } catch (error) {
      setErrorFactionDetail(error.message || "Failed to load faction");
    } finally {
      setLoadingFactionDetail(false);
    }
  }

  async function setFactionDetailPolicyAreaFilter(policyArea) {
    if (!selectedFactionId) return;
    setFactionDetailPolicyAreaFilterState(policyArea);
    setLoadingFactionDetail(true);
    try {
      const params = policyArea ? { policyArea } : {};
      const data = await getFaction(selectedFactionId, params);
      setFactionDetail(data);
    } catch (error) {
      setErrorFactionDetail(error.message || "Failed to load faction");
    } finally {
      setLoadingFactionDetail(false);
    }
  }

  function closeSessionDetail() {
    setSelectedSessionId(null);
    setSessionDetail(null);
    setErrorSessionDetail("");
  }

  async function openSessionDetail(sessionId) {
    setSelectedSessionId(sessionId);
    setSessionDetail(null);
    setErrorSessionDetail("");
    setLoadingSessionDetail(true);
    try {
      const data = await getSession(sessionId);
      setSessionDetail(data);
    } catch (error) {
      setErrorSessionDetail(error.message || "Failed to load session");
    } finally {
      setLoadingSessionDetail(false);
    }
  }

  async function openVoteDetail(voteId) {
    setSelectedVoteId(voteId);
    setVoteDetail(null);
    setErrorVoteDetail("");
    setLoadingVoteDetail(true);
    try {
      const data = await getVote(voteId);
      setVoteDetail(data);
    } catch (error) {
      setErrorVoteDetail(error.message || "Failed to load vote");
    } finally {
      setLoadingVoteDetail(false);
    }
  }

  async function handleImportSubmit(event) {
    event.preventDefault();
    setStatusMessage("Import queued...");
    try {
      await createImport(importForm);
      await refreshImports();
      setStatusMessage("Import queued successfully.");
    } catch (error) {
      const msg =
        error?.message ||
        (error?.rawBody ? `Server error: ${error.rawBody.slice(0, 200)}` : null) ||
        "Import failed";
      setStatusMessage(`Import failed: ${msg}`);
    }
  }

  const hasNoData =
    stats != null &&
    (stats.total_sessions ?? 0) === 0 &&
    (stats.total_votes ?? 0) === 0 &&
    (stats.total_persons ?? 0) === 0 &&
    (stats.total_factions ?? 0) === 0;

  const isExeOrigin =
    typeof window !== "undefined" &&
    (window.location?.hostname === "127.0.0.1" || window.location?.hostname === "localhost") &&
    window.location?.port !== "5173";

  function handleQuitApp() {
    setShuttingDown(true);
    quitApp().catch(() => {});
  }

  async function handleReloadData() {
    setReloadingData(true);
    try {
      await Promise.all([
        withRetry(getStats, 2, 500).then(setStats).catch(() => setStats(null)),
        withRetry(refreshImports, 2, 500).catch(() => {}),
      ]);
    } finally {
      setReloadingData(false);
    }
  }

  return (
    <div className="page">
      <header>
        <h1>Riigikogu Stats</h1>
        <p>Import and explore sessions + votes.</p>
        {healthInfo?.database_path != null && (
          <p className="db-path">Using database: {healthInfo.database_path}</p>
        )}
        <button
          type="button"
          className="reload-data"
          onClick={handleReloadData}
          disabled={reloadingData}
        >
          {reloadingData ? "Reloading…" : "Reload data"}
        </button>
        {isExeOrigin && (
          <button
            type="button"
            className="quit-app"
            onClick={handleQuitApp}
            disabled={shuttingDown}
          >
            {shuttingDown ? "Shutting down…" : "Quit app"}
          </button>
        )}
      </header>

      {stats != null && (
        <p className="data-scope">
          Data: {stats.min_session_date ?? "—"} – {stats.max_session_date ?? "—"}
          {" · "}
          {stats.total_sessions ?? 0} sessions · {stats.total_votes ?? 0} votes · {stats.total_persons ?? 0} persons · {stats.total_factions ?? 0} factions
        </p>
      )}

      {hasNoData && (
        <p className="no-data-hint">
          No data in the database yet. Use <strong>Import</strong> to load data from the Riigikogu API.
        </p>
      )}

      {!apiReady && (
        <div className="status">Server starting up, please wait...</div>
      )}

      {statusMessage && <div className="status">{statusMessage}</div>}

      <nav className="main-tabs" aria-label="Main sections">
        <button
          type="button"
          className={mainTab === "dashboard" ? "active" : ""}
          onClick={() => setMainTab("dashboard")}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={mainTab === "analytics" ? "active" : ""}
          onClick={() => setMainTab("analytics")}
        >
          Analytics
        </button>
      </nav>

      {mainTab === "dashboard" && (
      <section className="card">
        <h2>Download and store data</h2>
        <p className="section-desc">
          Fetch sessions and votes from the Riigikogu API for a date range and store them in the database. Use &quot;Init DB schema&quot; on first run.
        </p>
        <form onSubmit={handleImportSubmit} className="form-grid">
          <label>
            Start date
            <input
              type="date"
              value={importForm.startDate}
              onChange={(event) =>
                setImportForm({ ...importForm, startDate: event.target.value })
              }
            />
          </label>
          <label>
            End date
            <input
              type="date"
              value={importForm.endDate}
              onChange={(event) =>
                setImportForm({ ...importForm, endDate: event.target.value })
              }
            />
          </label>
          <label>
            Step days
            <input
              type="number"
              min="1"
              value={importForm.stepDays}
              onChange={(event) =>
                setImportForm({ ...importForm, stepDays: Number(event.target.value) })
              }
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={importForm.onlyVotings}
              onChange={(event) =>
                setImportForm({ ...importForm, onlyVotings: event.target.checked })
              }
            />
            Only votings
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={importForm.onlySittings}
              onChange={(event) =>
                setImportForm({ ...importForm, onlySittings: event.target.checked })
              }
            />
            Only sittings
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={importForm.initDb}
              onChange={(event) =>
                setImportForm({ ...importForm, initDb: event.target.checked })
              }
            />
            Init DB schema
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={importForm.syncUsergroups}
              onChange={(event) =>
                setImportForm({ ...importForm, syncUsergroups: event.target.checked })
              }
            />
            Sync factions and membership (usergroups)
          </label>
          <button type="submit" disabled={!apiReady}>Import</button>
        </form>

        {importCurrentRun != null && (
          <div className="import-live-log">
            <h3>Import {importCurrentRun.status === "queued" ? "queued" : "in progress"} (run #{importCurrentRun.id})</h3>
            <p className="import-live-summary">
              {importCurrentRun.items_processed} processed, {importCurrentRun.items_skipped} skipped
            </p>
            <div
              className="import-live-log-lines"
              role="log"
              aria-live="polite"
            >
              {importLogs.map((entry) => (
                <div key={entry.id} className="import-log-line">
                  <span className="import-log-time">{entry.logged_at}</span>{" "}
                  {entry.message}
                </div>
              ))}
            </div>
          </div>
        )}

        <h3>Import history</h3>
        {loadingImports && <p className="loading">Loading…</p>}
        {errorImports && <p className="error">{errorImports}</p>}
        <table>
          <thead>
            <tr>
              <th>Started</th>
              <th>Status</th>
              <th>Range</th>
              <th>Processed</th>
              <th>Skipped</th>
            </tr>
          </thead>
          <tbody>
            {importHistory.map((run) => (
              <tr key={run.id}>
                <td>{new Date(run.started_at).toLocaleString()}</td>
                <td>{run.status}</td>
                <td>
                  {run.start_date} → {run.end_date}
                </td>
                <td>{run.items_processed}</td>
                <td>{run.items_skipped}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      )}

      {mainTab === "analytics" && (
      <>
      <section className="card">
        <div className="section-header">
          <h2>Sessions</h2>
          <button type="button" onClick={() => refreshSessions()} disabled={loadingSessions}>
            {loadingSessions ? "Loading…" : "Refresh"}
          </button>
        </div>
        {errorSessions && <p className="error">{errorSessions}</p>}
        {sessionTotal != null && (
          <p className="total">Total: {sessionTotal} session(s)</p>
        )}
        <div className="form-grid">
          <label>
            Start date
            <input
              type="date"
              value={sessionFilters.startDate}
              onChange={(event) =>
                setSessionFilters({ ...sessionFilters, startDate: event.target.value })
              }
            />
          </label>
          <label>
            End date
            <input
              type="date"
              value={sessionFilters.endDate}
              onChange={(event) =>
                setSessionFilters({ ...sessionFilters, endDate: event.target.value })
              }
            />
          </label>
          <label>
            Status
            <input
              type="text"
              placeholder="present / absent"
              value={sessionFilters.status}
              onChange={(event) =>
                setSessionFilters({ ...sessionFilters, status: event.target.value })
              }
            />
          </label>
          <label>
            Sort by
            <select
              value={sessionSort.sortBy}
              onChange={(e) =>
                setSessionSort({ ...sessionSort, sortBy: e.target.value })
              }
            >
              <option value="session_date">Date</option>
              <option value="title">Title</option>
              <option value="attendance_count">Attendance count</option>
              <option value="present_count">Present count</option>
              <option value="absent_count">Absent count</option>
            </select>
          </label>
          <label>
            Order
            <select
              value={sessionSort.order}
              onChange={(e) =>
                setSessionSort({ ...sessionSort, order: e.target.value })
              }
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
          <button type="button" onClick={() => refreshSessions(0)}>
            Apply filters
          </button>
        </div>
        {!loadingSessions && sessions.length === 0 && (
          <p className="hint">Set filters and click Apply filters to load data.</p>
        )}
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Title</th>
              <th>Total</th>
              <th>Present</th>
              <th>Absent</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <tr key={session.id}>
                <td>{session.session_date}</td>
                <td>{session.title}</td>
                <td>{session.attendance_count}</td>
                <td>{session.present_count}</td>
                <td>{session.absent_count}</td>
                <td>
                  <button
                    type="button"
                    className="link"
                    onClick={() => openSessionDetail(session.id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sessionTotal != null && (
          <div className="pagination">
            <span className="pagination-info">
              Showing {sessionOffset + 1}–{Math.min(sessionOffset + (sessions?.length ?? 0), sessionTotal)} of {sessionTotal}
            </span>
            <button
              type="button"
              disabled={sessionOffset === 0 || loadingSessions}
              onClick={() => refreshSessions(Math.max(0, sessionOffset - sessionLimit))}
            >
              Previous
            </button>
            <button
              type="button"
              disabled={
                sessionOffset + (sessions?.length ?? 0) >= sessionTotal || loadingSessions
              }
              onClick={() => refreshSessions(sessionOffset + sessionLimit)}
            >
              Next
            </button>
          </div>
        )}
      </section>

      <section className="card">
        <div className="section-header">
          <h2>Votes</h2>
          <button type="button" onClick={() => refreshVotes()} disabled={loadingVotes}>
            {loadingVotes ? "Loading…" : "Refresh"}
          </button>
        </div>
        {errorVotes && <p className="error">{errorVotes}</p>}
        {voteTotal != null && (
          <p className="total">Total: {voteTotal} vote(s)</p>
        )}
        <div className="form-grid">
          <label>
            Start date
            <input
              type="date"
              value={voteFilters.startDate}
              onChange={(event) =>
                setVoteFilters({ ...voteFilters, startDate: event.target.value })
              }
            />
          </label>
          <label>
            End date
            <input
              type="date"
              value={voteFilters.endDate}
              onChange={(event) =>
                setVoteFilters({ ...voteFilters, endDate: event.target.value })
              }
            />
          </label>
          <label>
            Outcome
            <input
              type="text"
              placeholder="Accepted / Rejected"
              value={voteFilters.outcome}
              onChange={(event) =>
                setVoteFilters({ ...voteFilters, outcome: event.target.value })
              }
            />
          </label>
          <label>
            Choice
            <input
              type="text"
              placeholder="for / against / abstain"
              value={voteFilters.choice}
              onChange={(event) =>
                setVoteFilters({ ...voteFilters, choice: event.target.value })
              }
            />
          </label>
          <label>
            Search in subject/title
            <input
              type="text"
              placeholder="Subject or title contains…"
              value={voteFilters.subjectSearch}
              onChange={(event) =>
                setVoteFilters({ ...voteFilters, subjectSearch: event.target.value })
              }
            />
          </label>
          <label>
            Policy area
            <select
              value={voteFilters.policyArea}
              onChange={(e) =>
                setVoteFilters({ ...voteFilters, policyArea: e.target.value })
              }
            >
              <option value="">All</option>
              {POLICY_AREAS.map((pa) => (
                <option key={pa} value={pa}>{pa}</option>
              ))}
            </select>
          </label>
          <label>
            Sort by
            <select
              value={voteSort.sortBy}
              onChange={(e) =>
                setVoteSort({ ...voteSort, sortBy: e.target.value })
              }
            >
              <option value="vote_time">Time</option>
              <option value="title">Title</option>
              <option value="subject">Subject</option>
              <option value="result">Result</option>
              <option value="votes_for">Votes for</option>
              <option value="votes_against">Votes against</option>
              <option value="votes_abstain">Abstain</option>
              <option value="votes_did_not_vote">Did not vote</option>
            </select>
          </label>
          <label>
            Order
            <select
              value={voteSort.order}
              onChange={(e) =>
                setVoteSort({ ...voteSort, order: e.target.value })
              }
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
          <button type="button" onClick={() => refreshVotes(0)}>
            Apply filters
          </button>
          <button
            type="button"
            onClick={() => {
              const params = { sortBy: voteSort.sortBy, order: voteSort.order };
              if (voteFilters.startDate) params.startDate = voteFilters.startDate;
              if (voteFilters.endDate) params.endDate = voteFilters.endDate;
              if (voteFilters.outcome) params.outcome = voteFilters.outcome;
              if (voteFilters.choice) params.choice = voteFilters.choice;
              if (voteFilters.subjectSearch) params.subjectContains = voteFilters.subjectSearch;
              if (voteFilters.policyArea) params.policyArea = voteFilters.policyArea;
              window.location.href = getExportVotesUrl(params);
            }}
          >
            Export filtered votes (CSV)
          </button>
        </div>
        {!loadingVotes && votes.length === 0 && (
          <p className="hint">Set filters and click Apply filters to load data.</p>
        )}
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Session</th>
              <th>Title</th>
              <th>Result</th>
              <th>For</th>
              <th>Against</th>
              <th>Abstain</th>
              <th>Did not vote</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {votes.map((vote) => (
              <tr key={vote.id}>
                <td>{vote.vote_time ? new Date(vote.vote_time).toLocaleString() : ""}</td>
                <td>
                  {vote.session_id ? (
                    <button
                      type="button"
                      className="link"
                      onClick={() => openSessionDetail(vote.session_id)}
                    >
                      {vote.session_title ?? vote.session_date ?? vote.session_id}
                    </button>
                  ) : (
                    vote.session_title ?? vote.session_date ?? "—"
                  )}
                </td>
                <td>
                  <div>{vote.subject ?? vote.title}</div>
                  {vote.vote_type && (
                    <div className="vote-type">{vote.vote_type}</div>
                  )}
                  {vote.policy_area && (
                    <div className="policy-area">{vote.policy_area}</div>
                  )}
                </td>
                <td>{vote.result}</td>
                <td>{vote.votes_for}</td>
                <td>{vote.votes_against}</td>
                <td>{vote.votes_abstain}</td>
                <td>{vote.votes_did_not_vote}</td>
                <td>
                  <button
                    type="button"
                    className="link"
                    onClick={() => openVoteDetail(vote.id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {voteTotal != null && (
          <div className="pagination">
            <span className="pagination-info">
              Showing {voteOffset + 1}–{Math.min(voteOffset + (votes?.length ?? 0), voteTotal)} of {voteTotal}
            </span>
            <button
              type="button"
              disabled={voteOffset === 0 || loadingVotes}
              onClick={() => refreshVotes(Math.max(0, voteOffset - voteLimit))}
            >
              Previous
            </button>
            <button
              type="button"
              disabled={
                voteOffset + (votes?.length ?? 0) >= voteTotal || loadingVotes
              }
              onClick={() => refreshVotes(voteOffset + voteLimit)}
            >
              Next
            </button>
          </div>
        )}
      </section>

      <section className="card">
        <div className="section-header">
          <h2>Persons</h2>
          <button type="button" onClick={() => refreshPersons(0)}>Refresh</button>
        </div>
        {personTotal != null && (
          <p className="total">Total: {personTotal} person(s)</p>
        )}
        <div className="form-grid">
          <label>
            Sort by
            <select
              value={personSort.sortBy}
              onChange={(e) =>
                setPersonSort({ ...personSort, sortBy: e.target.value })
              }
            >
              <option value="votes_recorded">Votes recorded</option>
              <option value="full_name">Name</option>
              <option value="votes_for">Votes for</option>
              <option value="votes_against">Votes against</option>
              <option value="votes_abstain">Abstain</option>
              <option value="sessions_recorded">Sessions recorded</option>
              <option value="present_count">Present</option>
              <option value="absent_count">Absent</option>
              <option value="attendance_rate_pct">Attendance %</option>
            </select>
          </label>
          <label>
            Order
            <select
              value={personSort.order}
              onChange={(e) =>
                setPersonSort({ ...personSort, order: e.target.value })
              }
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
          <button type="button" onClick={() => refreshPersons(0)}>
            Apply
          </button>
        </div>
        {persons.length === 0 && (
          <p className="hint">Set sort options and click Apply to load data.</p>
        )}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Votes recorded</th>
              <th>For</th>
              <th>Against</th>
              <th>Abstain</th>
              <th>Did not vote</th>
              <th>Absent</th>
              <th>Sessions</th>
              <th>Attendance %</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {persons.map((p) => (
              <tr key={p.id}>
                <td>{p.full_name ?? p.id}</td>
                <td>{p.votes_recorded ?? 0}</td>
                <td>{p.votes_for ?? 0}</td>
                <td>{p.votes_against ?? 0}</td>
                <td>{p.votes_abstain ?? 0}</td>
                <td>{p.votes_did_not_vote ?? 0}</td>
                <td>{p.votes_absent ?? 0}</td>
                <td>{p.sessions_recorded ?? "—"}</td>
                <td>{p.attendance_rate_pct != null ? `${p.attendance_rate_pct}%` : "—"}</td>
                <td>
                  <button
                    type="button"
                    className="link"
                    onClick={() => openPersonDetail(p.id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {personTotal != null && (
          <div className="pagination">
            <span className="pagination-info">
              Showing {personOffset + 1}–{Math.min(personOffset + (persons?.length ?? 0), personTotal)} of {personTotal}
            </span>
            <button
              type="button"
              disabled={personOffset === 0}
              onClick={() => refreshPersons(Math.max(0, personOffset - personLimit))}
            >
              Previous
            </button>
            <button
              type="button"
              disabled={personOffset + (persons?.length ?? 0) >= personTotal}
              onClick={() => refreshPersons(personOffset + personLimit)}
            >
              Next
            </button>
          </div>
        )}
      </section>

      <section className="card">
        <div className="section-header">
          <h2>Factions</h2>
          <button type="button" onClick={() => refreshFactions(0)}>Refresh</button>
        </div>
        {factionTotal != null && (
          <p className="total">Total: {factionTotal} faction(s)</p>
        )}
        {factions.length === 0 && (
          <p className="hint">Click Refresh to load data.</p>
        )}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Total votes</th>
              <th>For</th>
              <th>Against</th>
              <th>Abstain</th>
              <th>Did not vote</th>
              <th>Absent</th>
              <th>Attendance %</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {factions.map((f) => (
              <tr key={f.id}>
                <td>{f.name ?? f.id}</td>
                <td>{f.total_votes ?? 0}</td>
                <td>{f.votes_for ?? 0}</td>
                <td>{f.votes_against ?? 0}</td>
                <td>{f.votes_abstain ?? 0}</td>
                <td>{f.votes_did_not_vote ?? 0}</td>
                <td>{f.votes_absent ?? 0}</td>
                <td>{f.attendance_rate_pct != null ? `${f.attendance_rate_pct}%` : "—"}</td>
                <td>
                  <button
                    type="button"
                    className="link"
                    onClick={() => openFactionDetail(f.id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {factionTotal != null && (
          <div className="pagination">
            <span className="pagination-info">
              Showing {factionOffset + 1}–{Math.min(factionOffset + (factions?.length ?? 0), factionTotal)} of {factionTotal}
            </span>
            <button
              type="button"
              disabled={factionOffset === 0}
              onClick={() => refreshFactions(Math.max(0, factionOffset - factionLimit))}
            >
              Previous
            </button>
            <button
              type="button"
              disabled={factionOffset + (factions?.length ?? 0) >= factionTotal}
              onClick={() => refreshFactions(factionOffset + factionLimit)}
            >
              Next
            </button>
          </div>
        )}
      </section>
      </>
      )}

      {selectedVoteId != null && (
        <div className="modal-overlay" onClick={closeVoteDetail} role="presentation">
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <div className="section-header">
              <h2>Vote detail</h2>
              <button type="button" onClick={closeVoteDetail}>Close</button>
            </div>
            {loadingVoteDetail && <p className="loading">Loading…</p>}
            {errorVoteDetail && <p className="error">{errorVoteDetail}</p>}
            {!loadingVoteDetail && !errorVoteDetail && voteDetail && (
              <>
                <p className="vote-detail-title">
                  <strong>What they&apos;re voting on:</strong>{" "}
                  {voteDetail.subject ?? voteDetail.title}
                </p>
                {voteDetail.vote_type && (
                  <p className="vote-detail-type">Type: {voteDetail.vote_type}</p>
                )}
                {voteDetail.policy_area && (
                  <p className="vote-detail-policy-area">Policy area: {voteDetail.policy_area}</p>
                )}
                <p>
                  <strong>Result:</strong> {voteDetail.result ?? "—"}
                  {voteDetail.vote_time && (
                    <> · {new Date(voteDetail.vote_time).toLocaleString()}</>
                  )}
                </p>
                {(voteDetail.session_title || voteDetail.session_date) && (
                  <p>
                    <strong>Session:</strong>{" "}
                    {voteDetail.session_title ?? voteDetail.session_id}
                    {voteDetail.session_date && ` (${voteDetail.session_date})`}
                    {voteDetail.session_id && (
                      <>
                        {" · "}
                        <button
                          type="button"
                          className="link"
                          onClick={() => {
                            closeVoteDetail();
                            openSessionDetail(voteDetail.session_id);
                          }}
                        >
                          See all votes in this session
                        </button>
                      </>
                    )}
                  </p>
                )}
                <table>
                  <thead>
                    <tr>
                      <th>Member</th>
                      <th>Choice</th>
                      <th>Faction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(voteDetail.casts ?? []).map((c, i) => (
                      <tr key={c.person_id ?? i}>
                        <td>{c.full_name ?? c.person_id}</td>
                        <td>{c.choice ?? "—"}</td>
                        <td>{c.faction_name ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>
      )}

      {selectedSessionId != null && (
        <div className="modal-overlay" onClick={closeSessionDetail} role="presentation">
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <div className="section-header">
              <h2>Session detail</h2>
              <button type="button" onClick={closeSessionDetail}>Close</button>
            </div>
            {loadingSessionDetail && <p className="loading">Loading…</p>}
            {errorSessionDetail && <p className="error">{errorSessionDetail}</p>}
            {!loadingSessionDetail && !errorSessionDetail && sessionDetail && (
              <>
                <p><strong>{sessionDetail.title ?? sessionDetail.id}</strong></p>
                {sessionDetail.session_date && (
                  <p>Date: {sessionDetail.session_date}</p>
                )}
                {(sessionDetail.votes?.length ?? 0) > 0 && (
                  <>
                    <p><strong>Votes in this session</strong></p>
                    <table>
                      <thead>
                        <tr>
                          <th>Time</th>
                          <th>Subject / Title</th>
                          <th>Result</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {sessionDetail.votes.map((v) => (
                          <tr key={v.id}>
                            <td>{v.vote_time ? new Date(v.vote_time).toLocaleString() : "—"}</td>
                            <td>{v.subject ?? v.title ?? "—"}</td>
                            <td>{v.result ?? "—"}</td>
                            <td>
                              <button
                                type="button"
                                className="link"
                                onClick={() => {
                                  closeSessionDetail();
                                  openVoteDetail(v.id);
                                }}
                              >
                                View
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {selectedPersonId != null && (
        <div className="modal-overlay" onClick={closePersonDetail} role="presentation">
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <div className="section-header">
              <h2>Person detail</h2>
              <button type="button" onClick={closePersonDetail}>Close</button>
            </div>
            {loadingPersonDetail && <p className="loading">Loading…</p>}
            {errorPersonDetail && <p className="error">{errorPersonDetail}</p>}
            {!loadingPersonDetail && !errorPersonDetail && personDetail && (
              <>
                <p><strong>{personDetail.full_name ?? personDetail.id}</strong></p>
                {personDetail.birth_date && (
                  <p>Birth date: {personDetail.birth_date}</p>
                )}
                <p>
                  Votes recorded: {personDetail.votes_recorded ?? 0} · For: {personDetail.votes_for ?? 0} · Against: {personDetail.votes_against ?? 0} · Abstain: {personDetail.votes_abstain ?? 0} · Did not vote: {personDetail.votes_did_not_vote ?? 0} · Absent: {personDetail.votes_absent ?? 0}
                </p>
                {(personDetail.sessions_recorded != null || personDetail.present_count != null) && (
                  <p>
                    Attendance: {personDetail.attendance_rate_pct != null ? `${personDetail.attendance_rate_pct}%` : "—"}
                    {personDetail.sessions_recorded != null && (
                      <> · Present at {personDetail.present_count ?? 0} of {personDetail.sessions_recorded} sessions</>
                    )}
                  </p>
                )}
                {(personDetail.recent_casts?.length ?? 0) > 0 && (
                  <>
                    <p><strong>Recent votes</strong></p>
                    <div className="filter-inline">
                      {(personDetail.vote_types?.length ?? 0) > 0 && (
                        <label className="filter-inline">
                          Show only vote type:{" "}
                          <select
                            value={personDetailVoteTypeFilter}
                            onChange={(e) => setPersonDetailVoteTypeFilter(e.target.value)}
                            disabled={loadingPersonDetail}
                          >
                            <option value="">All</option>
                            {(personDetail.vote_types ?? []).map((vt) => (
                              <option key={vt} value={vt}>{vt}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      <label className="filter-inline">
                        Policy area:{" "}
                        <select
                          value={personDetailPolicyAreaFilter}
                          onChange={(e) => setPersonDetailPolicyAreaFilter(e.target.value)}
                          disabled={loadingPersonDetail}
                        >
                          <option value="">All</option>
                          {POLICY_AREAS.map((pa) => (
                            <option key={pa} value={pa}>{pa}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <table>
                      <thead>
                        <tr>
                          <th>Vote</th>
                          <th>Type</th>
                          <th>Policy area</th>
                          <th>Choice</th>
                          <th>Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {personDetail.recent_casts.map((c, i) => (
                          <tr key={c.vote_id ?? i}>
                            <td>{c.subject ?? c.title ?? c.vote_id}</td>
                            <td>{c.vote_type ?? "—"}</td>
                            <td>{c.policy_area ?? "—"}</td>
                            <td>{c.choice ?? "—"}</td>
                            <td>{c.vote_time ? new Date(c.vote_time).toLocaleString() : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {selectedFactionId != null && (
        <div className="modal-overlay" onClick={closeFactionDetail} role="presentation">
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <div className="section-header">
              <h2>Faction detail</h2>
              <button type="button" onClick={closeFactionDetail}>Close</button>
            </div>
            {loadingFactionDetail && <p className="loading">Loading…</p>}
            {errorFactionDetail && <p className="error">{errorFactionDetail}</p>}
            {!loadingFactionDetail && !errorFactionDetail && factionDetail && (
              <>
                <p><strong>{factionDetail.name ?? factionDetail.id}</strong></p>
                <p>
                  Total votes: {factionDetail.total_votes ?? 0} · For: {factionDetail.votes_for ?? 0} · Against: {factionDetail.votes_against ?? 0} · Abstain: {factionDetail.votes_abstain ?? 0} · Did not vote: {factionDetail.votes_did_not_vote ?? 0} · Absent: {factionDetail.votes_absent ?? 0}
                </p>
                {(factionDetail.attendance_rate_pct != null || factionDetail.attendance_slots != null) && (
                  <p>
                    Attendance: {factionDetail.attendance_rate_pct != null ? `${factionDetail.attendance_rate_pct}%` : "—"}
                    {factionDetail.attendance_slots != null && (
                      <> · Present at {factionDetail.attendance_present ?? 0} of {factionDetail.attendance_slots} session–member records</>
                    )}
                  </p>
                )}
                <label className="filter-inline">
                  Policy area:{" "}
                  <select
                    value={factionDetailPolicyAreaFilter}
                    onChange={(e) => setFactionDetailPolicyAreaFilter(e.target.value)}
                    disabled={loadingFactionDetail}
                  >
                    <option value="">All</option>
                    {POLICY_AREAS.map((pa) => (
                      <option key={pa} value={pa}>{pa}</option>
                    ))}
                  </select>
                </label>
                {(factionDetail.votes_by_type?.length ?? 0) > 0 && (
                  <>
                    <p><strong>Votes by type</strong></p>
                    <table>
                      <thead>
                        <tr>
                          <th>Vote type</th>
                          <th>For</th>
                          <th>Against</th>
                          <th>Abstain</th>
                          <th>Did not vote</th>
                          <th>Absent</th>
                        </tr>
                      </thead>
                      <tbody>
                        {factionDetail.votes_by_type.map((row, i) => (
                          <tr key={row.vote_type ?? i}>
                            <td>{row.vote_type ?? "—"}</td>
                            <td>{row.votes_for ?? 0}</td>
                            <td>{row.votes_against ?? 0}</td>
                            <td>{row.votes_abstain ?? 0}</td>
                            <td>{row.votes_did_not_vote ?? 0}</td>
                            <td>{row.votes_absent ?? 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
                {(factionDetail.votes_by_policy_area?.length ?? 0) > 0 && (
                  <>
                    <p><strong>Votes by policy area</strong></p>
                    <table>
                      <thead>
                        <tr>
                          <th>Policy area</th>
                          <th>For</th>
                          <th>Against</th>
                          <th>Abstain</th>
                          <th>Did not vote</th>
                          <th>Absent</th>
                        </tr>
                      </thead>
                      <tbody>
                        {factionDetail.votes_by_policy_area.map((row, i) => (
                          <tr key={row.policy_area ?? i}>
                            <td>{row.policy_area ?? "—"}</td>
                            <td>{row.votes_for ?? 0}</td>
                            <td>{row.votes_against ?? 0}</td>
                            <td>{row.votes_abstain ?? 0}</td>
                            <td>{row.votes_did_not_vote ?? 0}</td>
                            <td>{row.votes_absent ?? 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
