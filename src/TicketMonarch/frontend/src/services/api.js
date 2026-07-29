import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function login(username, password) {
  const { data } = await api.post("/api/auth/login", { username, password });
  return data;
}

export async function register(username, password) {
  const { data } = await api.post("/api/auth/register", { username, password });
  return data;
}

export async function getCaptcha(difficulty, sessionId) {
  const { data } = await api.post("/api/captcha/generate", {
    difficulty: difficulty || 2,
    session_id: sessionId,
  });
  return data;
}

export async function verifyCaptcha(sessionId, payload) {
  const { data } = await api.post("/api/captcha/verify", {
    session_id: sessionId,
    ...payload,
  });
  return data;
}

const _telemetryQueue = [];
let _retryTimer = null;

function _flushRetryQueue() {
  if (_telemetryQueue.length === 0) {
    if (_retryTimer) { clearInterval(_retryTimer); _retryTimer = null; }
    return;
  }
  const item = _telemetryQueue.shift();
  api
    .post("/api/behavior/track", item)
    .catch(() => {
      if (_telemetryQueue.length < 20) _telemetryQueue.push(item);
    });
}

export async function trackBehavior(behaviorData) {
  try {
    const { data } = await api.post("/api/behavior/track", behaviorData);
    return data;
  } catch (err) {
    if (_telemetryQueue.length < 20) {
      _telemetryQueue.push(behaviorData);
      if (!_retryTimer) {
        _retryTimer = setInterval(_flushRetryQueue, 2000);
      }
    }
    throw err;
  }
}

export async function getRLDifficulty(behaviorData) {
  const { data } = await api.post("/api/rl/difficulty", behaviorData);
  return data;
}

export async function submitRLReward(rewardData) {
  const { data } = await api.post("/api/rl/reward", rewardData);
  return data;
}

export async function bookTicket(bookingData) {
  const { data } = await api.post("/api/booking/ticket", bookingData);
  return data;
}

export default api;
