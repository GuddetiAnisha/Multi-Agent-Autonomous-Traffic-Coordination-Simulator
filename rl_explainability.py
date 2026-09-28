"""Small reinforcement-learning and explainability extension.

This module is intentionally lightweight and software-only. It provides:
- a synthetic traffic-control environment derived from aggregate queue/conflict/utilization state,
- tabular Q-learning,
- local feature-importance explanations via one-feature perturbation, and
- temporal outcome explanations via short rollouts.

It is a portfolio/research prototype, not a production traffic controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import random


ACTIONS = ("hold", "grant_autonomous", "grant_manual")
FEATURES = ("queue_level", "conflict_level", "utilization_level")


@dataclass(frozen=True)
class RLState:
    queue_level: int
    conflict_level: int
    utilization_level: int

    def as_tuple(self):
        return (
            self.queue_level,
            self.conflict_level,
            self.utilization_level,
        )


class TrafficRLEnv:
    """Small aggregate traffic environment for controlled RL experiments."""

    def __init__(self, seed: int = 7, horizon: int = 60):
        self.rng = random.Random(seed)
        self.horizon = horizon
        self.step_count = 0
        self.state = RLState(1, 1, 1)

    def reset(self, state: RLState | None = None) -> RLState:
        self.step_count = 0
        self.state = state or RLState(
            self.rng.randint(0, 2),
            self.rng.randint(0, 2),
            self.rng.randint(0, 2),
        )
        return self.state

    def _transition(self, state: RLState, action: str) -> tuple[RLState, float]:
        if action not in ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        q, c, u = state.as_tuple()

        if action == "hold":
            next_q = min(2, q + (1 if q > 0 else 0))
            next_c = max(0, c - 1)
            next_u = max(0, u - 1)
            reward = -1.5 * q - 0.8 * next_q + 0.7 * (c - next_c)

        elif action == "grant_autonomous":
            next_q = max(0, q - 1)
            next_c = min(2, c + (1 if u == 2 else 0))
            next_u = min(2, u + 1)
            reward = 2.2 * (q - next_q) - 1.3 * next_c - 0.5 * next_u

        else:  # grant_manual
            next_q = max(0, q - 1)
            next_c = max(0, c - (1 if c > 0 else 0))
            next_u = min(2, u + 1)
            reward = 1.7 * (q - next_q) + 0.9 * (c - next_c) - 0.5 * next_u

        return RLState(next_q, next_c, next_u), reward

    def step(self, action: str):
        next_state, reward = self._transition(self.state, action)
        self.state = next_state
        self.step_count += 1
        done = self.step_count >= self.horizon
        return next_state, reward, done, {}

    def preview(self, state: RLState, action: str):
        return self._transition(state, action)


class QLearningAgent:
    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 0.9,
        epsilon: float = 0.2,
        seed: int = 7,
    ):
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.rng = random.Random(seed)
        self.q = defaultdict(lambda: {action: 0.0 for action in ACTIONS})

    def choose_action(self, state: RLState, explore: bool = True) -> str:
        if explore and self.rng.random() < self.epsilon:
            return self.rng.choice(ACTIONS)
        values = self.q[state.as_tuple()]
        return max(ACTIONS, key=lambda action: (values[action], action))

    def update(
        self,
        state: RLState,
        action: str,
        reward: float,
        next_state: RLState,
    ) -> None:
        current = self.q[state.as_tuple()][action]
        next_best = max(self.q[next_state.as_tuple()].values())
        target = reward + self.gamma * next_best
        self.q[state.as_tuple()][action] = current + self.alpha * (target - current)

    def train(self, env: TrafficRLEnv, episodes: int = 400) -> list[float]:
        rewards = []
        for _ in range(episodes):
            state = env.reset()
            total = 0.0
            done = False
            while not done:
                action = self.choose_action(state, explore=True)
                next_state, reward, done, _ = env.step(action)
                self.update(state, action, reward, next_state)
                state = next_state
                total += reward
            rewards.append(total)
        return rewards


def feature_importance_explanation(
    agent: QLearningAgent,
    state: RLState,
    action: str | None = None,
) -> dict[str, float]:
    """Local FI from one-feature perturbation of the chosen-action Q value."""
    action = action or agent.choose_action(state, explore=False)
    base = agent.q[state.as_tuple()][action]
    values = {}

    raw = list(state.as_tuple())
    for index, feature in enumerate(FEATURES):
        scores = []
        for alternative in (0, 1, 2):
            if alternative == raw[index]:
                continue
            changed = raw.copy()
            changed[index] = alternative
            score = agent.q[tuple(changed)][action]
            scores.append(abs(base - score))
        values[feature] = round(sum(scores) / max(1, len(scores)), 4)

    total = sum(values.values())
    if total:
        values = {name: round(value / total, 4) for name, value in values.items()}
    return values


def temporal_policy_decomposition(
    agent: QLearningAgent,
    env: TrafficRLEnv,
    state: RLState,
    action: str | None = None,
    horizon: int = 4,
) -> list[dict]:
    """Explain an action through predicted short-term outcomes."""
    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    action = action or agent.choose_action(state, explore=False)
    current = state
    selected = action
    outcomes = []

    for step_index in range(horizon):
        next_state, reward = env.preview(current, selected)
        outcomes.append(
            {
                "step": step_index + 1,
                "action": selected,
                "queue_level": next_state.queue_level,
                "conflict_level": next_state.conflict_level,
                "utilization_level": next_state.utilization_level,
                "predicted_reward": round(reward, 4),
            }
        )
        current = next_state
        selected = agent.choose_action(current, explore=False)

    return outcomes


def compare_explanations(
    agent: QLearningAgent,
    env: TrafficRLEnv,
    state: RLState,
) -> dict:
    action = agent.choose_action(state, explore=False)
    return {
        "state": {
            "queue_level": state.queue_level,
            "conflict_level": state.conflict_level,
            "utilization_level": state.utilization_level,
        },
        "selected_action": action,
        "feature_importance": feature_importance_explanation(agent, state, action),
        "temporal_policy_decomposition": temporal_policy_decomposition(
            agent,
            env,
            state,
            action,
        ),
    }
