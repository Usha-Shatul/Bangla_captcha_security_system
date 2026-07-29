import os
import sys
import json
import time
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.ppo import PPOAgent
from agent.softppo import SoftPPOAgent
from agent.dg import DualGeneratorAgent
from environment.captcha_env import CaptchaEnv
from environment.reward import RewardFunction
from features.extractor import FeatureExtractor
from environment.state import StateBuilder


CHECKPOINTS_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


class Trainer:
    def __init__(
        self,
        agent_type: str = "ppo",
        state_dim: int = 20,
        action_dim: int = 3,
        hidden_dim: int = 128,
        lstm_dim: int = 64,
        lr: float = 3e-4,
        gamma: float = 0.99,
        lam: float = 0.95,
        clip_epsilon: float = 0.2,
        entropy_coeff: float = 0.01,
        ppo_epochs: int = 10,
        mini_batch_size: int = 64,
        num_episodes: int = 1000,
        eval_interval: int = 50,
        save_interval: int = 100,
        max_steps_per_episode: int = 100,
        bot_ratio: float = 0.3,
        device: str = "cpu",
    ):
        self.agent_type = agent_type
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.num_episodes = num_episodes
        self.eval_interval = eval_interval
        self.save_interval = save_interval
        self.bot_ratio = bot_ratio
        self.device = device

        self.env = CaptchaEnv(
            state_dim=state_dim,
            difficulty_levels=action_dim,
            max_steps=max_steps_per_episode,
        )

        self.extractor = FeatureExtractor()
        self.state_builder = StateBuilder(feature_dim=state_dim)

        if agent_type == "ppo":
            self.agent = PPOAgent(
                obs_dim=state_dim,
                action_dim=action_dim,
                hidden_dim=hidden_dim,
                lstm_dim=lstm_dim,
                lr=lr,
                gamma=gamma,
                lam=lam,
                clip_epsilon=clip_epsilon,
                entropy_coeff=entropy_coeff,
                ppo_epochs=ppo_epochs,
                mini_batch_size=mini_batch_size,
                device=device,
            )
        elif agent_type == "softppo":
            self.agent = SoftPPOAgent(
                obs_dim=state_dim,
                action_dim=action_dim,
                hidden_dim=hidden_dim,
                lstm_dim=lstm_dim,
                lr=lr,
                gamma=gamma,
                lam=lam,
                clip_epsilon=clip_epsilon,
                entropy_coeff=entropy_coeff,
                ppo_epochs=ppo_epochs,
                mini_batch_size=mini_batch_size,
                device=device,
            )
        elif agent_type == "dg":
            self.agent = DualGeneratorAgent(
                obs_dim=state_dim,
                action_dim=action_dim,
                hidden_dim=hidden_dim,
                lstm_dim=lstm_dim,
                lr_actor=lr,
                gamma=gamma,
                lam=lam,
                clip_epsilon=clip_epsilon,
                entropy_coeff=entropy_coeff,
                ppo_epochs=ppo_epochs,
                mini_batch_size=mini_batch_size,
                device=device,
            )
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

        os.makedirs(CHECKPOINTS_DIR, exist_ok=True)

        self.training_log = []
        self.best_reward = -float("inf")

    def _simulate_session(self) -> dict:
        is_bot = np.random.random() < self.bot_ratio

        mouse_events = []
        keyboard_events = []

        if is_bot:
            n_mouse = np.random.randint(5, 20)
            for i in range(n_mouse):
                mouse_events.append({
                    "x": float(np.random.uniform(0, 1920)),
                    "y": float(np.random.uniform(0, 1080)),
                    "timestamp": float(i * np.random.uniform(1, 5)),
                    "button": 0,
                    "click_type": "",
                    "speed": float(np.random.uniform(0, 100)),
                })

            n_keys = np.random.randint(3, 15)
            for i in range(n_keys):
                t = float(i * np.random.uniform(20, 80))
                keyboard_events.append({
                    "type": "keydown",
                    "key": chr(np.random.randint(97, 123)),
                    "code": f"Key{chr(np.random.randint(65, 91))}",
                    "timestamp": t,
                })
                keyboard_events.append({
                    "type": "keyup",
                    "key": chr(np.random.randint(97, 123)),
                    "code": f"Key{chr(np.random.randint(65, 91))}",
                    "timestamp": t + np.random.uniform(10, 50),
                })
        else:
            n_mouse = np.random.randint(20, 100)
            base_t = 0.0
            for i in range(n_mouse):
                dt = np.random.exponential(30)
                base_t += dt
                speed = np.random.normal(500, 200)
                mouse_events.append({
                    "x": float(np.random.uniform(100, 1800)),
                    "y": float(np.random.uniform(100, 900)),
                    "timestamp": base_t,
                    "button": 0,
                    "click_type": "",
                    "speed": float(max(0, speed)),
                })

            n_keys = np.random.randint(10, 40)
            base_t = 0.0
            for i in range(n_keys):
                dt = np.random.exponential(80)
                base_t += dt
                key = chr(np.random.randint(97, 123))
                keyboard_events.append({
                    "type": "keydown",
                    "key": key,
                    "code": f"Key{key.upper()}",
                    "timestamp": base_t,
                })
                keyboard_events.append({
                    "type": "keyup",
                    "key": key,
                    "code": f"Key{key.upper()}",
                    "timestamp": base_t + np.random.normal(60, 20),
                })

        return {
            "is_bot": is_bot,
            "mouse_events": mouse_events,
            "keyboard_events": keyboard_events,
        }

    def _simulate_outcome(self, difficulty: int, is_bot: bool, features: dict) -> dict:
        if is_bot:
            correct_prob = max(0.1, 0.9 - difficulty * 0.25)
        else:
            correct_prob = max(0.3, 0.95 - difficulty * 0.1)

        is_correct = np.random.random() < correct_prob
        solve_time = np.random.exponential(3000 + difficulty * 1000)

        return {
            "is_correct": is_correct,
            "is_bot": is_bot,
            "solve_time_ms": solve_time,
        }

    def train(self) -> dict:
        print(f"Starting training: {self.agent_type.upper()}")
        print(f"Episodes: {self.num_episodes} | State: {self.state_dim} | Actions: {self.action_dim}")
        print("=" * 60)

        episode_rewards = []
        episode_lengths = []
        difficulty_history = []
        human_accuracies = []
        bot_accuracies = []

        total_human_correct = 0
        total_human_sessions = 0
        total_bot_correct = 0
        total_bot_sessions = 0

        start_time = time.time()

        for episode in range(self.num_episodes):
            session = self._simulate_session()
            is_bot = session["is_bot"]

            state = self.env.reset(
                mouse_events=session["mouse_events"],
                keyboard_events=session["keyboard_events"],
            )

            episode_reward = 0.0
            episode_length = 0
            difficulty_chosen = 1
            done = False

            while not done:
                action, log_prob, value = self.agent.select_action(state)
                difficulty = int(np.clip(action, 0, self.action_dim - 1)) + 1
                difficulty_chosen = difficulty

                next_state, _, done, info = self.env.step(action)

                outcome = self._simulate_outcome(difficulty, is_bot, {})

                reward = self.env.receive_outcome(
                    is_correct=outcome["is_correct"],
                    is_bot=outcome["is_bot"],
                    solve_time_ms=outcome["solve_time_ms"],
                )

                self.agent.store_transition(state, action, log_prob, reward, done, value)

                state = next_state
                episode_reward += reward
                episode_length += 1

                if is_bot:
                    total_bot_sessions += 1
                    if outcome["is_correct"]:
                        total_bot_correct += 1
                else:
                    total_human_sessions += 1
                    if outcome["is_correct"]:
                        total_human_correct += 1

            stats = self.agent.update()

            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
            difficulty_history.append(difficulty_chosen)

            human_acc = total_human_correct / max(total_human_sessions, 1)
            bot_acc = total_bot_correct / max(total_bot_sessions, 1)
            human_accuracies.append(human_acc)
            bot_accuracies.append(bot_acc)

            log_entry = {
                "episode": episode + 1,
                "reward": round(episode_reward, 4),
                "length": episode_length,
                "difficulty": difficulty_chosen,
                "human_acc": round(human_acc, 4),
                "bot_acc": round(bot_acc, 4),
                "stats": {k: round(v, 4) if isinstance(v, float) else v for k, v in stats.items()},
            }
            self.training_log.append(log_entry)

            if (episode + 1) % 10 == 0:
                avg_reward = np.mean(episode_rewards[-10:])
                avg_diff = np.mean(difficulty_history[-10:])
                elapsed = time.time() - start_time
                print(
                    f"Ep {episode + 1}/{self.num_episodes} | "
                    f"Reward: {avg_reward:.3f} | "
                    f"Diff: {avg_diff:.1f} | "
                    f"H-Acc: {human_acc:.3f} | "
                    f"B-Acc: {bot_acc:.3f} | "
                    f"Time: {elapsed:.1f}s"
                )

            if (episode + 1) % self.eval_interval == 0:
                eval_reward = np.mean(episode_rewards[-self.eval_interval:])
                print(f"\n--- Eval @ {episode + 1}: avg_reward={eval_reward:.4f} ---\n")

            if (episode + 1) % self.save_interval == 0:
                if episode_reward > self.best_reward:
                    self.best_reward = episode_reward
                    path = os.path.join(CHECKPOINTS_DIR, f"{self.agent_type}_best.pt")
                    self.agent.save(path)

                path = os.path.join(CHECKPOINTS_DIR, f"{self.agent_type}_ep{episode + 1}.pt")
                self.agent.save(path)

        final_path = os.path.join(CHECKPOINTS_DIR, f"{self.agent_type}_final.pt")
        self.agent.save(final_path)

        results = {
            "agent_type": self.agent_type,
            "episodes": self.num_episodes,
            "final_avg_reward": round(float(np.mean(episode_rewards[-50:])), 4),
            "final_human_accuracy": round(human_accuracies[-1], 4) if human_accuracies else 0,
            "final_bot_accuracy": round(bot_accuracies[-1], 4) if bot_accuracies else 0,
            "avg_difficulty": round(float(np.mean(difficulty_history[-50:])), 2) if difficulty_history else 1,
            "total_human_sessions": total_human_sessions,
            "total_bot_sessions": total_bot_sessions,
            "training_time_seconds": round(time.time() - start_time, 2),
            "save_path": final_path,
        }

        results_path = os.path.join(CHECKPOINTS_DIR, f"{self.agent_type}_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        log_path = os.path.join(CHECKPOINTS_DIR, f"{self.agent_type}_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.training_log, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 60)
        print("Training Complete!")
        print(f"Final avg reward: {results['final_avg_reward']}")
        print(f"Human accuracy: {results['final_human_accuracy']}")
        print(f"Bot accuracy: {results['final_bot_accuracy']}")
        print(f"Model saved: {final_path}")
        print("=" * 60)

        return results


def main():
    import argparse

    default_agent = os.environ.get("RL_ALGORITHM", "ppo")

    parser = argparse.ArgumentParser(description="Train RL agent for CAPTCHA difficulty")
    parser.add_argument("--agent", type=str, default=default_agent, choices=["ppo", "softppo", "soft_ppo", "dg"])
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--state-dim", type=int, default=20)
    parser.add_argument("--action-dim", type=int, default=3)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--lstm-dim", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--clip-epsilon", type=float, default=0.2)
    parser.add_argument("--entropy-coeff", type=float, default=0.01)
    parser.add_argument("--ppo-epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--eval-interval", type=int, default=50)
    parser.add_argument("--save-interval", type=int, default=100)
    parser.add_argument("--bot-ratio", type=float, default=0.3)
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    agent_type = args.agent
    if agent_type == "soft_ppo":
        agent_type = "softppo"

    trainer = Trainer(
        agent_type=agent_type,
        state_dim=args.state_dim,
        action_dim=args.action_dim,
        hidden_dim=args.hidden_dim,
        lstm_dim=args.lstm_dim,
        lr=args.lr,
        gamma=args.gamma,
        clip_epsilon=args.clip_epsilon,
        entropy_coeff=args.entropy_coeff,
        ppo_epochs=args.ppo_epochs,
        mini_batch_size=args.batch_size,
        num_episodes=args.episodes,
        eval_interval=args.eval_interval,
        save_interval=args.save_interval,
        bot_ratio=args.bot_ratio,
        device=args.device,
    )

    trainer.train()


if __name__ == "__main__":
    main()
