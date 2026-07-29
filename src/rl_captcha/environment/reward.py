import numpy as np
from typing import Optional
from environment.security_actions import SECURITY_ACTIONS, action_name


class RewardFunction:
    def __init__(
        self,
        correct_reward: float = 1.0,
        incorrect_reward: float = -0.5,
        timeout_reward: float = -0.3,
        bot_caught_reward: float = 0.8,
        bot_passed_reward: float = -1.0,
        difficulty_bonus_factor: float = 0.2,
        max_attempts_penalty: float = -0.2,
        time_pressure_weight: float = 0.1,
        human_pass_weight: float = 0.3,
        difficulty_match_weight: float = 0.2,
        block_penalty_human: float = -2.0,
        block_reward_bot: float = 1.5,
        honeypot_reward_bot: float = 1.2,
        honeypot_penalty_human: float = -0.8,
        allow_reward_trusted: float = 0.5,
        allow_penalty_bot: float = -1.5,
        observe_reward: float = 0.1,
    ):
        self.correct_reward = correct_reward
        self.incorrect_reward = incorrect_reward
        self.timeout_reward = timeout_reward
        self.bot_caught_reward = bot_caught_reward
        self.bot_passed_reward = bot_passed_reward
        self.difficulty_bonus_factor = difficulty_bonus_factor
        self.max_attempts_penalty = max_attempts_penalty
        self.time_pressure_weight = time_pressure_weight
        self.human_pass_weight = human_pass_weight
        self.difficulty_match_weight = difficulty_match_weight
        self.block_penalty_human = block_penalty_human
        self.block_reward_bot = block_reward_bot
        self.honeypot_reward_bot = honeypot_reward_bot
        self.honeypot_penalty_human = honeypot_penalty_human
        self.allow_reward_trusted = allow_reward_trusted
        self.allow_penalty_bot = allow_penalty_bot
        self.observe_reward = observe_reward

    def compute(
        self,
        is_correct: Optional[bool] = None,
        is_bot: bool = False,
        difficulty: int = 1,
        solve_time_ms: float = 0.0,
        attempt_count: int = 0,
        max_attempts: int = 3,
        total_sessions: int = 0,
        human_pass_rate: float = 0.5,
        bot_pass_rate: float = 0.0,
        action: int = 2,
    ) -> tuple[float, dict]:
        reward = 0.0
        breakdown = {}
        action_name_str = action_name(action)

        if action == 0:
            if is_bot:
                reward += self.allow_penalty_bot
                breakdown["allow_bot_penalty"] = self.allow_penalty_bot
            else:
                reward += self.allow_reward_trusted
                breakdown["allow_trusted"] = self.allow_reward_trusted
            breakdown["action"] = "allow"

        elif action == 1:
            reward += self.observe_reward
            breakdown["observe"] = self.observe_reward
            breakdown["action"] = "observe"

        elif action in (2, 3, 4):
            breakdown["action"] = action_name_str
            if is_correct is None:
                reward += self.timeout_reward
                breakdown["timeout"] = self.timeout_reward
            elif is_correct:
                reward += self.correct_reward
                breakdown["correct"] = self.correct_reward

                difficulty_bonus = (difficulty - 1) * self.difficulty_bonus_factor
                reward += difficulty_bonus
                breakdown["difficulty_bonus"] = difficulty_bonus

                if is_bot:
                    reward += self.bot_caught_reward
                    breakdown["bot_caught"] = self.bot_caught_reward
                else:
                    reward += self.human_pass_weight
                    breakdown["human_pass"] = self.human_pass_weight
            else:
                reward += self.incorrect_reward
                breakdown["incorrect"] = self.incorrect_reward

                if is_bot:
                    reward -= self.bot_passed_reward
                    breakdown["bot_passed"] = -self.bot_passed_reward

            if attempt_count >= max_attempts and not is_correct:
                reward += self.max_attempts_penalty
                breakdown["max_attempts"] = self.max_attempts_penalty

        elif action == 5:
            breakdown["action"] = "honeypot"
            if is_bot:
                reward += self.honeypot_reward_bot
                breakdown["honeypot_bot"] = self.honeypot_reward_bot
            else:
                reward += self.honeypot_penalty_human
                breakdown["honeypot_human"] = self.honeypot_penalty_human

        elif action == 6:
            breakdown["action"] = "block"
            if is_bot:
                reward += self.block_reward_bot
                breakdown["block_bot"] = self.block_reward_bot
            else:
                reward += self.block_penalty_human
                breakdown["block_human"] = self.block_penalty_human

        if solve_time_ms > 0 and action in (2, 3, 4):
            time_pressure = self._compute_time_pressure(solve_time_ms)
            reward += time_pressure
            breakdown["time_pressure"] = time_pressure

        if difficulty > 1 and is_correct and not is_bot and action in (2, 3, 4):
            level_bonus = difficulty * 0.1
            reward += level_bonus
            breakdown["high_difficulty_human"] = level_bonus

        breakdown["total"] = reward
        return reward, breakdown

    def _compute_time_pressure(self, solve_time_ms: float) -> float:
        if solve_time_ms < 1000:
            return -self.time_pressure_weight
        elif solve_time_ms < 3000:
            return 0.0
        elif solve_time_ms < 10000:
            return self.time_pressure_weight * 0.5
        else:
            return self.time_pressure_weight

    def compute_batch_rewards(
        self,
        episodes: list[dict],
    ) -> list[float]:
        rewards = []
        for ep in episodes:
            reward, _ = self.compute(
                is_correct=ep.get("is_correct"),
                is_bot=ep.get("is_bot", False),
                difficulty=ep.get("difficulty", 1),
                solve_time_ms=ep.get("solve_time_ms", 0),
                attempt_count=ep.get("attempt_count", 0),
                action=ep.get("action", 2),
            )
            rewards.append(reward)
        return rewards

    def to_dict(self) -> dict:
        return {
            "correct_reward": self.correct_reward,
            "incorrect_reward": self.incorrect_reward,
            "timeout_reward": self.timeout_reward,
            "bot_caught_reward": self.bot_caught_reward,
            "bot_passed_reward": self.bot_passed_reward,
            "difficulty_bonus_factor": self.difficulty_bonus_factor,
            "max_attempts_penalty": self.max_attempts_penalty,
            "time_pressure_weight": self.time_pressure_weight,
            "human_pass_weight": self.human_pass_weight,
            "difficulty_match_weight": self.difficulty_match_weight,
            "block_penalty_human": self.block_penalty_human,
            "block_reward_bot": self.block_reward_bot,
            "honeypot_reward_bot": self.honeypot_reward_bot,
            "honeypot_penalty_human": self.honeypot_penalty_human,
            "allow_reward_trusted": self.allow_reward_trusted,
            "allow_penalty_bot": self.allow_penalty_bot,
            "observe_reward": self.observe_reward,
        }
