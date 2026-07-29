import os
import json
import logging
import numpy as np

from config import Config

log = logging.getLogger(__name__)

_predictor = None
_simple_agent = None
_predictor_checked = False


SECURITY_ACTIONS = {
    0: "allow",
    1: "observe",
    2: "captcha_easy",
    3: "captcha_medium",
    4: "captcha_hard",
    5: "honeypot",
    6: "block",
}

_AGENT_TYPES = {"ppo", "softppo", "soft_ppo", "dg"}


def _normalize_agent_type(agent_type: str) -> str:
    """Map soft_ppo -> softppo, pass others through."""
    if agent_type == "soft_ppo":
        return "softppo"
    return agent_type


def _get_predictor():
    global _predictor, _predictor_checked
    if _predictor_checked:
        return _predictor
    _predictor_checked = True

    agent_type = _normalize_agent_type(Config.RL_ALGORITHM)
    if agent_type not in _AGENT_TYPES:
        log.warning("Invalid RL_ALGORITHM=%r — falling back to ppo", Config.RL_ALGORITHM)
        agent_type = "ppo"

    try:
        from rl_captcha.inference.predict import CaptchaPredictor
        ckpt_dir = Config.RL_CHECKPOINT_DIR
        model_path = os.path.join(ckpt_dir, f"{agent_type}_best.pt")

        if not os.path.isfile(model_path):
            model_path = os.path.join(ckpt_dir, f"{agent_type}_final.pt")

        if not os.path.isfile(model_path):
            log.warning(
                "No checkpoint found for agent_type=%s in %s — using SimpleRL agent",
                agent_type, ckpt_dir,
            )
            return None

        predictor = CaptchaPredictor(agent_type=agent_type, model_path=model_path)
        if predictor.is_loaded:
            _predictor = predictor
            log.info("Loaded %s predictor from %s", agent_type.upper(), model_path)
        else:
            log.warning("Failed to load %s checkpoint — using SimpleRL agent", agent_type)
    except Exception as e:
        log.warning("Predictor unavailable (%s) — using SimpleRL agent", e)
    return _predictor


def _get_simple_agent():
    global _simple_agent
    if _simple_agent is None:
        _simple_agent = SimpleRLAgent()
    return _simple_agent


class SimpleRLAgent:
    def __init__(self):
        self.num_actions = 7
        self.q_table_path = os.path.join(Config.RL_CHECKPOINT_DIR, "q_table.json")
        self.q_table = self._load_q_table()

    def _load_q_table(self) -> dict:
        if os.path.isfile(self.q_table_path):
            with open(self.q_table_path, "r") as f:
                return json.load(f)
        return {}

    def _save_q_table(self):
        os.makedirs(os.path.dirname(self.q_table_path), exist_ok=True)
        with open(self.q_table_path, "w") as f:
            json.dump(self.q_table, f)

    def _state_key(self, features: dict) -> str:
        bot_score_bin = int(min(features.get("bot_score", 0), 1.0) * 10)
        rhythm_bin = min(int(features.get("typing_rhythm_std", 0) / 50), 5)
        speed_bin = min(int(features.get("avg_mouse_speed", 0) / 1000), 5)
        return f"{bot_score_bin}_{rhythm_bin}_{speed_bin}"

    def get_action(self, features: dict, epsilon: float = 0.1) -> int:
        state = self._state_key(features)

        if np.random.random() < epsilon:
            return np.random.randint(0, self.num_actions)

        if state in self.q_table:
            q_vals = self.q_table[state]
            return int(np.argmax(q_vals))

        return 2

    def get_difficulty(self, features: dict, epsilon: float = 0.1) -> int:
        action = self.get_action(features, epsilon)
        return _action_to_difficulty(action)

    def update(self, features: dict, action: int, reward: float,
               lr: float = 0.1, gamma: float = 0.9):
        state = self._state_key(features)

        if state not in self.q_table:
            self.q_table[state] = [0.0] * self.num_actions

        self.q_table[state][action] += lr * reward
        self._save_q_table()


def _action_to_difficulty(action: int) -> int:
    mapping = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 1, 6: 0}
    return mapping.get(action, 1)


def get_rl_agent():
    return _get_simple_agent()


def get_security_action(features: dict, keyboard_events=None, mouse_events=None,
                        previous_difficulty: int = 1, attempt_count: int = 0,
                        session_duration_ms: float = 0.0,
                        bot_score: float = 0.0, confidence: float = 0.5) -> dict:
    predictor = _get_predictor()
    if predictor is not None and predictor.is_loaded:
        try:
            result = predictor.predict_action(
                mouse_events=mouse_events or [],
                keyboard_events=keyboard_events or [],
                previous_difficulty=previous_difficulty,
                attempt_count=attempt_count,
                session_duration_ms=session_duration_ms,
                bot_score=bot_score,
                confidence=confidence,
            )
            return result
        except Exception as e:
            log.warning("Predictor predict failed: %s — falling back to SimpleRL", e)

    agent = _get_simple_agent()
    action = agent.get_action(features)
    action_name = SECURITY_ACTIONS.get(action, "unknown")
    difficulty = _action_to_difficulty(action)

    decision_map = {
        0: {"type": "allow", "description": "Trusted — skip CAPTCHA"},
        1: {"type": "observe", "description": "Collect more data"},
        2: {"type": "captcha", "difficulty": 1, "description": "Easy CAPTCHA"},
        3: {"type": "captcha", "difficulty": 2, "description": "Medium CAPTCHA"},
        4: {"type": "captcha", "difficulty": 3, "description": "Hard CAPTCHA"},
        5: {"type": "honeypot", "description": "Fake CAPTCHA trap"},
        6: {"type": "block", "description": "Session blocked"},
    }

    return {
        "action": action,
        "action_name": action_name,
        "difficulty": difficulty,
        "decision": decision_map.get(action, {"type": "unknown"}),
    }


def get_difficulty(features: dict, keyboard_events=None, mouse_events=None,
                   previous_difficulty: int = 1, attempt_count: int = 0,
                   session_duration_ms: float = 0.0,
                   bot_score: float = 0.0, confidence: float = 0.5) -> int:
    result = get_security_action(
        features=features,
        keyboard_events=keyboard_events,
        mouse_events=mouse_events,
        previous_difficulty=previous_difficulty,
        attempt_count=attempt_count,
        session_duration_ms=session_duration_ms,
        bot_score=bot_score,
        confidence=confidence,
    )
    return result["difficulty"]


def update_rl(features: dict, action: int, reward: float,
              keyboard_events=None, mouse_events=None, done: bool = False,
              previous_difficulty: int = 1, attempt_count: int = 0,
              session_duration_ms: float = 0.0,
              bot_score: float = 0.0, confidence: float = 0.5):
    predictor = _get_predictor()
    if predictor is not None and predictor.is_loaded:
        try:
            predictor.update(
                mouse_events=mouse_events or [],
                keyboard_events=keyboard_events or [],
                action=action,
                reward=reward,
                done=done,
                previous_difficulty=previous_difficulty,
                attempt_count=attempt_count,
                session_duration_ms=session_duration_ms,
                bot_score=bot_score,
                confidence=confidence,
            )
            return
        except Exception as e:
            log.warning("Predictor update failed: %s — falling back to SimpleRL", e)

    agent = _get_simple_agent()
    agent.update(features, action, reward)
