import { useState, useEffect, useRef, useCallback } from "react";
import api from "../services/api.js";

const ACTION_LABELS = {
  allow: { label: "Allow", color: "#16a34a", icon: "✓" },
  observe: { label: "Observe", color: "#d97706", icon: "⏳" },
  captcha_easy: { label: "Easy CAPTCHA", color: "#2563eb", icon: "🔐" },
  captcha_medium: { label: "Medium CAPTCHA", color: "#7c3aed", icon: "🔐" },
  captcha_hard: { label: "Hard CAPTCHA", color: "#dc2626", icon: "🔐" },
  honeypot: { label: "Honeypot", color: "#a855f7", icon: "🪤" },
  block: { label: "Block", color: "#991b1b", icon: "✕" },
};

export default function DevDashboard() {
  const [sessions, setSessions] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionDetail, setSessionDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef(null);

  const fetchSessions = useCallback(async () => {
    try {
      const [sessRes, statsRes] = await Promise.all([
        api.get("/api/dev/sessions?limit=20"),
        api.get("/api/behavior/stats"),
      ]);
      if (sessRes.data?.ok) setSessions(sessRes.data.sessions);
      if (statsRes.data?.ok) setStats(statsRes.data);
      setError("");
    } catch (err) {
      setError("Failed to load sessions");
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    pollRef.current = setInterval(fetchSessions, 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchSessions]);

  const selectSession = async (sessionId) => {
    setSelectedSession(sessionId);
    setLoadingDetail(true);
    setSessionDetail(null);
    try {
      const res = await api.get(`/api/dev/session/${sessionId}`);
      if (res.data?.ok) setSessionDetail(res.data);
      else setError(res.data?.error || "Session not found");
    } catch (err) {
      setError("Failed to load session detail");
    } finally {
      setLoadingDetail(false);
    }
  };

  const latest = sessions[0];

  return (
    <div className="dev-dashboard">
      <header className="dev-header">
        <h1>Dev Dashboard</h1>
        <div className="dev-header-meta">
          <span className="dev-pulse" />
          <span>Live — polling every 1s</span>
        </div>
      </header>

      {error && <div className="dev-error">{error}</div>}

      <div className="dev-grid">
        <section className="dev-panel dev-live-monitor">
          <h2>Live Monitor</h2>
          {latest && (
            <div className="dev-latest-card">
              <div className="dev-latest-row">
                <span className="dev-label">Active Session</span>
                <span className="dev-mono">{latest.session_id}</span>
              </div>
              <div className="dev-latest-row">
                <span className="dev-label">Bot Score</span>
                <span className={`dev-score ${latest.is_bot ? "bot" : "human"}`}>
                  {latest.bot_score.toFixed(3)}
                </span>
              </div>
              <div className="dev-latest-row">
                <span className="dev-label">Mouse Events</span>
                <span>{latest.mouse_events}</span>
              </div>
              <div className="dev-latest-row">
                <span className="dev-label">Keyboard Events</span>
                <span>{latest.keyboard_events}</span>
              </div>
              <div className="dev-latest-row">
                <span className="dev-label">Method</span>
                <span className="dev-badge">{latest.method}</span>
              </div>
              <div className="dev-latest-row">
                <span className="dev-label">Classification</span>
                <span className={latest.is_bot ? "dev-bot-tag" : "dev-human-tag"}>
                  {latest.is_bot ? "BOT" : "HUMAN"}
                </span>
              </div>
            </div>
          )}

          {stats && (
            <div className="dev-stats-row">
              <div className="dev-stat">
                <span className="dev-stat-val">{stats.total_sessions}</span>
                <span className="dev-stat-label">Total</span>
              </div>
              <div className="dev-stat">
                <span className="dev-stat-val dev-bot-color">{stats.detected_bots}</span>
                <span className="dev-stat-label">Bots</span>
              </div>
              <div className="dev-stat">
                <span className="dev-stat-val dev-human-color">{stats.human_sessions}</span>
                <span className="dev-stat-label">Human</span>
              </div>
              <div className="dev-stat">
                <span className="dev-stat-val">{stats.avg_bot_score.toFixed(3)}</span>
                <span className="dev-stat-label">Avg Score</span>
              </div>
            </div>
          )}
        </section>

        <section className="dev-panel dev-session-list">
          <h2>Recent Sessions</h2>
          <div className="dev-session-scroll">
            {sessions.map((s) => (
              <div
                key={s.session_id}
                className={`dev-session-row ${selectedSession === s.session_id ? "selected" : ""}`}
                onClick={() => selectSession(s.session_id)}
              >
                <span className="dev-mono dev-session-id">{s.session_id}</span>
                <span className={`dev-score-sm ${s.is_bot ? "bot" : "human"}`}>
                  {s.bot_score.toFixed(2)}
                </span>
                <span className="dev-session-events">
                  🖱{s.mouse_events} ⌨{s.keyboard_events}
                </span>
                <span className="dev-session-time">
                  {s.created_at ? new Date(s.created_at).toLocaleTimeString() : ""}
                </span>
              </div>
            ))}
            {sessions.length === 0 && (
              <div className="dev-empty">No sessions yet. Start the checkout flow to generate data.</div>
            )}
          </div>
        </section>
      </div>

      {selectedSession && (
        <section className="dev-panel dev-analyze">
          <h2>Analyze Session — {selectedSession}</h2>
          {loadingDetail ? (
            <div className="dev-loading">Loading analysis...</div>
          ) : sessionDetail ? (
            <AnalyzeSession data={sessionDetail} />
          ) : (
            <div className="dev-empty">No data for this session.</div>
          )}
        </section>
      )}

      <style>{devStyles}</style>
    </div>
  );
}


function AnalyzeSession({ data }) {
  const { session, security_action, action_probs, feature_breakdown, timeline, state_vector } = data;
  const actionName = security_action?.action_name || "unknown";
  const actionInfo = ACTION_LABELS[actionName] || { label: actionName, color: "#666", icon: "?" };

  return (
    <div className="analyze-root">
      <div
        className="analyze-decision-banner"
        style={{ borderColor: actionInfo.color }}
      >
        <span className="analyze-decision-icon" style={{ color: actionInfo.color }}>
          {actionInfo.icon}
        </span>
        <div>
          <div className="analyze-decision-label" style={{ color: actionInfo.color }}>
            {actionInfo.label}
          </div>
          <div className="analyze-decision-desc">
            {security_action?.decision?.description || "N/A"}
          </div>
        </div>
        <div className="analyze-decision-meta">
          <span>Bot: {session.is_bot ? "YES" : "NO"}</span>
          <span>Score: {session.bot_score.toFixed(3)}</span>
          <span>Conf: {session.confidence.toFixed(3)}</span>
        </div>
      </div>

      <div className="analyze-columns">
        <div className="analyze-col">
          <h3>Action Probabilities</h3>
          <div className="analyze-bars">
            {Object.entries(action_probs).map(([name, prob]) => {
              const info = ACTION_LABELS[name] || { label: name, color: "#666" };
              return (
                <div key={name} className="analyze-bar-row">
                  <span className="analyze-bar-label">{info.label}</span>
                  <div className="analyze-bar-track">
                    <div
                      className="analyze-bar-fill"
                      style={{
                        width: `${Math.max(prob * 100, 1)}%`,
                        background: info.color,
                      }}
                    />
                  </div>
                  <span className="analyze-bar-val">{(prob * 100).toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="analyze-col">
          <h3>Feature Breakdown</h3>
          <div className="analyze-features">
            {Object.entries(feature_breakdown).map(([key, val]) => (
              <div key={key} className="analyze-feature-row">
                <span className="analyze-feature-key">{key}</span>
                <span className="analyze-feature-val">
                  {typeof val === "number" ? val.toFixed(4) : String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {state_vector && state_vector.length > 0 && (
        <div className="analyze-section">
          <h3>LSTM Hidden State</h3>
          <LSTMHeatmap vector={state_vector} />
        </div>
      )}

      <div className="analyze-section">
        <h3>Event Timeline ({timeline.length} events)</h3>
        <EventTimeline events={timeline} />
      </div>
    </div>
  );
}


function LSTMHeatmap({ vector }) {
  const maxVal = Math.max(...vector.map(Math.abs), 0.001);
  const cols = Math.min(vector.length, 10);
  const rows = Math.ceil(vector.length / cols);

  return (
    <div className="heatmap-grid" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {vector.map((val, i) => {
        const norm = val / maxVal;
        const hue = norm >= 0 ? 210 : 0;
        const sat = Math.min(Math.abs(norm) * 80, 100);
        const light = 25 + Math.abs(norm) * 35;
        return (
          <div
            key={i}
            className="heatmap-cell"
            style={{ background: `hsl(${hue}, ${sat}%, ${light}%)` }}
            title={`dim_${i}: ${val.toFixed(4)}`}
          >
            <span className="heatmap-val">{val.toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
}


function EventTimeline({ events }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="timeline-container" ref={containerRef}>
      {events.map((ev, i) => (
        <div
          key={i}
          className={`timeline-event ${ev.type}`}
        >
          <span className="timeline-time">
            {ev.timestamp ? `${ev.timestamp.toFixed(0)}ms` : ""}
          </span>
          <span className={`timeline-dot ${ev.type}`} />
          <span className="timeline-detail">
            {ev.type === "mouse" ? (
              <>
                ({ev.x?.toFixed(0)}, {ev.y?.toFixed(0)})
                {ev.speed > 0 && ` · ${ev.speed.toFixed(0)}px/s`}
                {ev.click && " · CLICK"}
              </>
            ) : (
              <>
                "{ev.key}"
                {ev.hold > 0 && ` · ${ev.hold}ms hold`}
                {ev.interval > 0 && ` · ${ev.interval}ms gap`}
              </>
            )}
          </span>
        </div>
      ))}
      {events.length === 0 && (
        <div className="dev-empty">No events recorded for this session.</div>
      )}
    </div>
  );
}


const devStyles = `
  .dev-dashboard {
    padding: 20px clamp(16px, 4vw, 56px);
    max-width: 1400px;
    margin: 0 auto;
  }
  .dev-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid rgba(212,169,79,.2);
  }
  .dev-header h1 {
    margin: 0; font-family: var(--serif-display); font-size: 1.6rem;
    color: var(--cream);
  }
  .dev-header-meta {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.85rem; color: rgba(242,234,223,.5);
  }
  .dev-pulse {
    width: 8px; height: 8px; border-radius: 50%; background: #16a34a;
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .dev-error {
    background: rgba(224,122,107,.12); border: 1px solid rgba(224,122,107,.3);
    color: #E07A6B; padding: 10px 14px; border-radius: 8px; font-size: 13px;
    margin-bottom: 16px;
  }
  .dev-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
    margin-bottom: 20px;
  }
  @media (max-width: 860px) { .dev-grid { grid-template-columns: 1fr; } }
  .dev-panel {
    background: var(--night-2); border: 1px solid rgba(212,169,79,.15);
    border-radius: 12px; padding: 20px;
  }
  .dev-panel h2 {
    margin: 0 0 14px; font-size: 1rem; color: var(--cream);
    font-family: var(--serif-display);
  }
  .dev-panel h3 {
    margin: 0 0 10px; font-size: 0.9rem; color: rgba(242,234,223,.7);
  }
  .dev-latest-card {
    background: var(--night); border-radius: 8px; padding: 14px;
    margin-bottom: 14px;
  }
  .dev-latest-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 5px 0; font-size: 0.85rem;
  }
  .dev-label { color: rgba(242,234,223,.5); }
  .dev-mono { font-family: monospace; color: var(--cream); font-size: 0.8rem; }
  .dev-score { font-weight: 700; font-size: 1.1rem; }
  .dev-score.bot { color: #E07A6B; }
  .dev-score.human { color: #3f8f6c; }
  .dev-badge {
    background: rgba(212,169,79,.15); color: var(--gold-soft);
    padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;
  }
  .dev-bot-tag {
    background: rgba(224,122,107,.15); color: #E07A6B;
    padding: 2px 10px; border-radius: 4px; font-weight: 700; font-size: 0.8rem;
  }
  .dev-human-tag {
    background: rgba(63,143,108,.15); color: #3f8f6c;
    padding: 2px 10px; border-radius: 4px; font-weight: 700; font-size: 0.8rem;
  }
  .dev-stats-row {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
  }
  .dev-stat {
    text-align: center; padding: 10px; background: var(--night);
    border-radius: 8px;
  }
  .dev-stat-val {
    display: block; font-size: 1.2rem; font-weight: 700; color: var(--cream);
  }
  .dev-stat-label {
    display: block; font-size: 0.7rem; color: rgba(242,234,223,.45);
    margin-top: 2px;
  }
  .dev-bot-color { color: #E07A6B; }
  .dev-human-color { color: #3f8f6c; }
  .dev-session-scroll {
    max-height: 300px; overflow-y: auto;
  }
  .dev-session-row {
    display: grid; grid-template-columns: 120px 50px 1fr auto;
    gap: 10px; align-items: center; padding: 8px 10px;
    border-radius: 6px; cursor: pointer; font-size: 0.82rem;
    transition: background 0.1s;
  }
  .dev-session-row:hover { background: rgba(212,169,79,.08); }
  .dev-session-row.selected { background: rgba(212,169,79,.15); }
  .dev-session-id { overflow: hidden; text-overflow: ellipsis; }
  .dev-score-sm { font-weight: 600; }
  .dev-score-sm.bot { color: #E07A6B; }
  .dev-score-sm.human { color: #3f8f6c; }
  .dev-session-events { color: rgba(242,234,223,.5); font-size: 0.75rem; }
  .dev-session-time { color: rgba(242,234,223,.35); font-size: 0.75rem; }
  .dev-empty { color: rgba(242,234,223,.35); font-size: 0.85rem; padding: 20px 0; text-align: center; }
  .dev-loading { color: rgba(242,234,223,.5); padding: 20px; text-align: center; }

  .dev-analyze { grid-column: 1 / -1; }
  .analyze-root { }
  .analyze-decision-banner {
    display: flex; align-items: center; gap: 16px;
    border: 2px solid; border-radius: 10px; padding: 16px 20px;
    margin-bottom: 20px; background: var(--night);
  }
  .analyze-decision-icon { font-size: 2rem; }
  .analyze-decision-label { font-weight: 700; font-size: 1.1rem; }
  .analyze-decision-desc { color: rgba(242,234,223,.5); font-size: 0.85rem; margin-top: 2px; }
  .analyze-decision-meta {
    margin-left: auto; display: flex; gap: 16px;
    font-size: 0.8rem; color: rgba(242,234,223,.5);
  }
  .analyze-columns {
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
    margin-bottom: 20px;
  }
  @media (max-width: 860px) { .analyze-columns { grid-template-columns: 1fr; } }
  .analyze-bars { }
  .analyze-bar-row {
    display: grid; grid-template-columns: 110px 1fr 50px;
    gap: 8px; align-items: center; margin-bottom: 6px;
  }
  .analyze-bar-label { font-size: 0.78rem; color: rgba(242,234,223,.6); }
  .analyze-bar-track {
    height: 14px; background: var(--night); border-radius: 4px; overflow: hidden;
  }
  .analyze-bar-fill {
    height: 100%; border-radius: 4px; transition: width 0.3s;
  }
  .analyze-bar-val { font-size: 0.75rem; color: rgba(242,234,223,.5); text-align: right; }
  .analyze-features { }
  .analyze-feature-row {
    display: flex; justify-content: space-between; padding: 4px 0;
    border-bottom: 1px solid rgba(242,234,223,.06); font-size: 0.82rem;
  }
  .analyze-feature-key { color: rgba(242,234,223,.5); font-family: monospace; font-size: 0.78rem; }
  .analyze-feature-val { color: var(--cream); font-family: monospace; font-size: 0.78rem; }
  .analyze-section { margin-bottom: 20px; }
  .heatmap-grid {
    display: grid; gap: 3px; max-width: 500px;
  }
  .heatmap-cell {
    aspect-ratio: 1.6; border-radius: 3px; display: flex;
    align-items: center; justify-content: center;
    position: relative; overflow: hidden;
  }
  .heatmap-val {
    font-size: 0.6rem; color: rgba(255,255,255,.7);
    font-family: monospace;
  }
  .timeline-container {
    max-height: 300px; overflow-y: auto; padding: 8px;
    background: var(--night); border-radius: 8px;
  }
  .timeline-event {
    display: flex; align-items: center; gap: 8px;
    padding: 3px 0; font-size: 0.78rem;
  }
  .timeline-time {
    width: 70px; text-align: right; color: rgba(242,234,223,.3);
    font-family: monospace; font-size: 0.7rem;
  }
  .timeline-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  }
  .timeline-dot.mouse { background: #2563eb; }
  .timeline-dot.keyboard { background: #16a34a; }
  .timeline-detail { color: rgba(242,234,223,.6); }
`;
