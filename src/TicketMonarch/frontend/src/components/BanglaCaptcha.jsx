import { useState, useEffect, useCallback, useRef } from "react";
import { getCaptcha, verifyCaptcha, trackBehavior } from "../services/api.js";

const SECURITY_DECISIONS = {
  allow: { label: "অনুমতি দেওয়া হয়েছে", color: "#16a34a", icon: "✓" },
  observe: { label: "পর্যবেক্ষণ করা হচ্ছে", color: "#d97706", icon: "⏳" },
  captcha: { label: "ক্যাপচা প্রয়োজন", color: "#2563eb", icon: "🔐" },
  honeypot: { label: "নিরাপত্তা পরীক্ষা", color: "#7c3aed", icon: "🔒" },
  block: { label: "ব্লক করা হয়েছে", color: "#dc2626", icon: "✕" },
};

export default function BanglaCaptcha({
  sessionId,
  behaviorData,
  onSecurityAction,
  onVerified,
}) {
  const [securityAction, setSecurityAction] = useState(null);
  const [captchaData, setCaptchaData] = useState(null);
  const [captchaType, setCaptchaType] = useState(null);
  const [userInput, setUserInput] = useState("");
  const [selectedPositions, setSelectedPositions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState(0);
  const [difficulty, setDifficulty] = useState(2);
  const startTimeRef = useRef(null);
  const pollRef = useRef(null);
  const isSolvingRef = useRef(false);
  const lastActionNameRef = useRef(null);

  const getSecurityDecision = useCallback(async () => {
    if (!behaviorData) return;
    try {
      const payload = {
        mouse: behaviorData?.mouse?.events || [],
        keyboard: behaviorData?.keyboard?.events || [],
        previous_difficulty: difficulty,
        attempt_count: attempts,
        session_duration_ms: behaviorData?.session_duration_ms || 0,
      };
      const result = await trackBehavior(payload);
      if (result?.security_action) {
        const newName = result.security_action.action_name;
        if (isSolvingRef.current && newName === lastActionNameRef.current) {
          return result.security_action;
        }
        lastActionNameRef.current = newName;
        setSecurityAction(result.security_action);
        onSecurityAction?.(result.security_action);
        return result.security_action;
      }
    } catch (err) {
      console.warn("Behavior track failed:", err);
    }
    return null;
  }, [behaviorData, difficulty, attempts, onSecurityAction]);

  const fetchCaptcha = useCallback(
    async (diff) => {
      setLoading(true);
      setError("");
      setUserInput("");
      setSelectedPositions([]);
      try {
        const data = await getCaptcha(diff || difficulty, sessionId);
        if (data?.ok) {
          setCaptchaData(data);
          setCaptchaType(data.captcha_type);
          setDifficulty(data.difficulty || difficulty);
          startTimeRef.current = Date.now();
          isSolvingRef.current = true;
        } else {
          setError(data?.error || "ক্যাপচা লোড করা যায়নি।");
        }
      } catch (err) {
        setError("ক্যাপচা লোড করা যায়নি। আবার চেষ্টা করুন।");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, difficulty]
  );

  useEffect(() => {
    if (securityAction && securityAction.action_name?.startsWith("captcha")) {
      if (!isSolvingRef.current) {
        isSolvingRef.current = true;
        fetchCaptcha(securityAction.difficulty);
      }
    }
  }, [securityAction, fetchCaptcha]);

  useEffect(() => {
    pollRef.current = setInterval(() => {
      if (!isSolvingRef.current) {
        getSecurityDecision();
      }
    }, 3000);
    getSecurityDecision();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [getSecurityDecision]);

  const togglePosition = (pos) => {
    setSelectedPositions((prev) =>
      prev.includes(pos) ? prev.filter((p) => p !== pos) : [...prev, pos]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    isSolvingRef.current = false;
    setLoading(true);
    setError("");
    const solveTime = Date.now() - (startTimeRef.current || Date.now());

    let payload = {
      solve_time_ms: solveTime,
      mouse: behaviorData?.mouse?.events || [],
      keyboard: behaviorData?.keyboard?.events || [],
      difficulty,
    };

    if (captchaType === "easy") {
      payload.words = userInput;
    } else if (captchaType === "medium") {
      payload.selected_positions = selectedPositions;
      payload.words = [];
    }

    try {
      const result = await verifyCaptcha(sessionId, payload);

      if (result?.correct) {
        if (result?.security_action) {
          setSecurityAction(result.security_action);
        }
        onVerified?.({ ...result, security_action: result?.security_action || securityAction });
      } else {
        setAttempts((a) => a + 1);
        setError(`ভুল উত্তর। আর ${3 - attempts - 1}টি চেষ্টা বাকি।`);
        fetchCaptcha(result?.security_action?.difficulty || difficulty);
      }
    } catch (err) {
      setError(err.response?.data?.error || "যাচাইকরণে সমস্যা হয়েছে।");
      fetchCaptcha();
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    isSolvingRef.current = false;
    setAttempts((a) => a + 1);
    fetchCaptcha();
  };

  if (!securityAction) {
    return (
      <div className="bangla-captcha">
        <h3>নিরাপত্তা পরীক্ষা</h3>
        <div className="captcha-loading">আচরণ বিশ্লেষণ হচ্ছে...</div>
        <style>{captchaStyles}</style>
      </div>
    );
  }

  const actionType = securityAction.action_name || "captcha";
  const actionInfo = SECURITY_DECISIONS[actionType] || SECURITY_DECISIONS.captcha;

  if (actionType === "allow") {
    return (
      <div className="bangla-captcha">
        <h3>নিরাপত্তা পরীক্ষা</h3>
        <div className="captcha-decision" style={{ borderColor: actionInfo.color }}>
          <span className="decision-icon" style={{ color: actionInfo.color }}>
            {actionInfo.icon}
          </span>
          <p style={{ color: actionInfo.color, fontWeight: 600 }}>{actionInfo.label}</p>
          <p className="decision-sub">
            আপনার আচরণ যাচাই করা হয়েছে। ক্যাপচা প্রয়োজন নেই।
          </p>
        </div>
        <style>{captchaStyles}</style>
      </div>
    );
  }

  if (actionType === "block") {
    return (
      <div className="bangla-captcha">
        <h3>নিরাপত্তা পরীক্ষা</h3>
        <div className="captcha-decision" style={{ borderColor: actionInfo.color }}>
          <span className="decision-icon" style={{ color: actionInfo.color }}>
            {actionInfo.icon}
          </span>
          <p style={{ color: actionInfo.color, fontWeight: 600 }}>{actionInfo.label}</p>
          <p className="decision-sub">
            সন্দেহজনক আচরণ সনাক্ত করা হয়েছে। সেশন ব্লক করা হয়েছে।
          </p>
        </div>
        <style>{captchaStyles}</style>
      </div>
    );
  }

  if (actionType === "observe") {
    return (
      <div className="bangla-captcha">
        <h3>নিরাপত্তা পরীক্ষা</h3>
        <div className="captcha-decision" style={{ borderColor: actionInfo.color }}>
          <span className="decision-icon" style={{ color: actionInfo.color }}>
            {actionInfo.icon}
          </span>
          <p style={{ color: actionInfo.color, fontWeight: 600 }}>{actionInfo.label}</p>
          <p className="decision-sub">
            আরও তথ্য সংগ্রহ করা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।
          </p>
        </div>
        <style>{captchaStyles}</style>
      </div>
    );
  }

  const isHoneypot = actionType === "honeypot";
  const isMedium = captchaType === "medium";
  const isEasy = captchaType === "easy";

  return (
    <div className="bangla-captcha">
      <h3>
        {isMedium
          ? "ছবি ক্যাপচা সমাধান করুন"
          : "বাংলা ক্যাপচা সমাধান করুন"}
      </h3>

      <div className="captcha-difficulty-bar">
        <span className="difficulty-label">কঠিনতা স্তর: {difficulty}</span>
        <span className="action-badge" style={{ background: actionInfo.color }}>
          {actionInfo.icon} {actionInfo.label}
        </span>
      </div>

      <div className="captcha-display">
        {loading ? (
          <div className="captcha-loading">লোড হচ্ছে...</div>
        ) : isMedium && captchaData ? (
          <div className="captcha-medium-wrap">
            <p className="captcha-target">
              নির্বাচন করুন:{" "}
              <strong>{captchaData.target_label_bn}</strong>
            </p>
            <div className="captcha-grid">
              {captchaData.grid.map((cell) => (
                <button
                  key={cell.position}
                  type="button"
                  className={`captcha-grid-cell ${
                    selectedPositions.includes(cell.position) ? "selected" : ""
                  }`}
                  onClick={() => togglePosition(cell.position)}
                >
                  <img src={cell.image} alt={`position ${cell.position}`} />
                  <span className="cell-check">
                    {selectedPositions.includes(cell.position) ? "✓" : ""}
                  </span>
                </button>
              ))}
            </div>
            <p className="captcha-hint">
              {selectedPositions.length}টি ছবি নির্বাচিত
            </p>
          </div>
        ) : isEasy && captchaData ? (
          <div className="captcha-easy-wrap">
            <img
              src={captchaData.image}
              alt="CAPTCHA"
              className="captcha-easy-image"
            />
          </div>
        ) : (
          <div className="captcha-loading">ক্যাপচা লোড হচ্ছে...</div>
        )}
      </div>

      {isHoneypot && (
        <p className="captcha-honeypot-hint">
          এটি একটি নিরাপত্তা পরীক্ষা। শুধুমাত্র মানব ব্যবহারকারীরা এটি সমাধান করতে পারবেন।
        </p>
      )}

      <button
        type="button"
        className="captcha-refresh"
        onClick={handleRefresh}
        disabled={loading}
      >
        নতুন ক্যাপচা
      </button>

      <form onSubmit={handleSubmit}>
        {isEasy ? (
          <input
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            placeholder="ছবিতে যা লেখা আছে তা লিখুন..."
            className="captcha-input"
            disabled={loading}
            autoComplete="off"
            autoFocus
          />
        ) : isMedium ? (
          <button
            type="submit"
            className="captcha-submit captcha-submit-full"
            disabled={loading || selectedPositions.length === 0}
          >
            {loading
              ? "যাচাই হচ্ছে..."
              : `যাচাই করুন (${selectedPositions.length}টি নির্বাচিত)`}
          </button>
        ) : null}

        {isEasy && (
          <button
            type="submit"
            className="captcha-submit"
            disabled={loading || !userInput.trim()}
          >
            {loading ? "যাচাই হচ্ছে..." : "যাচাই করুন"}
          </button>
        )}
      </form>

      {error && <p className="captcha-error">{error}</p>}

      <div className="captcha-meta">
        <span>চেষ্টা: {attempts}/3</span>
        <span>কঠিনতা: স্তর {difficulty}</span>
      </div>

      <style>{captchaStyles}</style>
    </div>
  );
}

const captchaStyles = `
  .bangla-captcha {
    border: 1px solid rgba(212,169,79,.25);
    border-radius: var(--radius);
    padding: 24px;
    max-width: 500px;
    text-align: center;
    background: var(--night-2);
    margin-top: 18px;
  }
  .bangla-captcha h3 {
    margin: 0 0 16px;
    font-size: 1.1rem;
    color: var(--cream);
    font-family: var(--serif-display);
  }
  .captcha-decision {
    border: 2px solid;
    border-radius: 12px;
    padding: 32px 24px;
    text-align: center;
  }
  .decision-icon {
    font-size: 2.5rem;
    display: block;
    margin-bottom: 12px;
  }
  .decision-sub {
    color: rgba(242,234,223,.55);
    font-size: 0.85rem;
    margin-top: 8px;
  }
  .captcha-difficulty-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .difficulty-label {
    font-size: 0.8rem;
    color: rgba(242,234,223,.55);
  }
  .action-badge {
    font-size: 0.75rem;
    color: #fff;
    padding: 3px 10px;
    border-radius: 999px;
    font-weight: 500;
  }
  .captcha-display {
    min-height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--night);
    border: 2px dashed rgba(212,169,79,.3);
    border-radius: 8px;
    margin-bottom: 12px;
    overflow: hidden;
    padding: 12px;
  }
  .captcha-loading {
    color: rgba(242,234,223,.5);
    padding: 32px;
  }
  .captcha-easy-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
  }
  .captcha-easy-image {
    max-width: 100%;
    max-height: 200px;
    border-radius: 6px;
    border: 1px solid rgba(212,169,79,.3);
  }
  .captcha-medium-wrap {
    width: 100%;
  }
  .captcha-target {
    margin: 0 0 12px;
    font-size: 1rem;
    color: var(--cream);
  }
  .captcha-target strong {
    color: var(--gold-soft);
    font-size: 1.15rem;
    font-family: var(--serif-display);
  }
  .captcha-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    max-width: 360px;
    margin: 0 auto;
  }
  .captcha-grid-cell {
    position: relative;
    aspect-ratio: 1;
    border: 2px solid rgba(212,169,79,.25);
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    background: var(--night-2);
    padding: 0;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .captcha-grid-cell:hover {
    border-color: var(--gold-soft);
  }
  .captcha-grid-cell.selected {
    border-color: var(--gold);
    box-shadow: 0 0 0 2px rgba(212,169,79,.4);
  }
  .captcha-grid-cell img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    pointer-events: none;
  }
  .cell-check {
    position: absolute;
    bottom: 4px;
    right: 4px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--gold);
    color: var(--night);
    font-size: 14px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .captcha-grid-cell.selected .cell-check {
    opacity: 1;
  }
  .captcha-hint {
    margin: 8px 0 0;
    font-size: 0.8rem;
    color: rgba(242,234,223,.5);
  }
  .captcha-honeypot-hint {
    color: #b794f4;
    font-size: 0.8rem;
    font-style: italic;
    margin-bottom: 12px;
  }
  .captcha-refresh {
    background: none;
    border: 1px solid rgba(212,169,79,.4);
    color: var(--gold-soft);
    border-radius: 6px;
    padding: 6px 14px;
    cursor: pointer;
    font-size: 0.85rem;
    margin-bottom: 16px;
  }
  .captcha-refresh:hover:not(:disabled) {
    background: rgba(212,169,79,.1);
  }
  .bangla-captcha form {
    display: flex;
    gap: 8px;
  }
  .captcha-input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid rgba(212,169,79,.3);
    border-radius: 8px;
    font-size: 1rem;
    outline: none;
    direction: ltr;
    background: var(--night);
    color: var(--cream);
    font-family: var(--body);
  }
  .captcha-input:focus {
    border-color: var(--gold);
    box-shadow: 0 0 0 2px rgba(212,169,79,.2);
  }
  .captcha-submit {
    padding: 10px 20px;
    background: linear-gradient(140deg, var(--gold-soft), var(--gold));
    color: var(--night);
    border: none;
    border-radius: 8px;
    font-size: 0.95rem;
    cursor: pointer;
    white-space: nowrap;
    font-weight: 600;
  }
  .captcha-submit:hover:not(:disabled) {
    filter: brightness(1.08);
  }
  .captcha-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .captcha-submit-full {
    width: 100%;
    padding: 12px 20px;
  }
  .captcha-error {
    color: #E07A6B;
    font-size: 0.9rem;
    margin: 12px 0 0;
  }
  .captcha-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: rgba(242,234,223,.4);
    margin-top: 12px;
  }
`;
