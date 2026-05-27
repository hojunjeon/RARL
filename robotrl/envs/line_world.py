from __future__ import annotations

import random
from dataclasses import dataclass, field


ActionMap = dict[str, int]
ObservationMap = dict[str, tuple[int, int, int, int]]
RewardMap = dict[str, float]


@dataclass
class LineWorldEnv:
    length: int = 7
    max_steps: int = 12
    agent_count: int = 2
    seed: int | None = None
    positions: dict[str, int] = field(init=False, default_factory=dict)
    targets: dict[str, int] = field(init=False, default_factory=dict)
    step_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.length < 3:
            raise ValueError("length must be at least 3")
        if self.agent_count < 2:
            raise ValueError("agent_count must be at least 2")
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")
        self._rng = random.Random(self.seed)
        self.agent_ids = tuple(f"agent_{index}" for index in range(self.agent_count))

    def reset(self) -> ObservationMap:
        self.step_count = 0
        middle = self.length // 2
        self.targets = {agent_id: middle for agent_id in self.agent_ids}
        self.positions = {
            agent_id: 0 if index % 2 == 0 else self.length - 1
            for index, agent_id in enumerate(self.agent_ids)
        }
        return self._observations()

    def step(self, actions: ActionMap) -> tuple[ObservationMap, RewardMap, bool, dict[str, object]]:
        if set(actions) != set(self.agent_ids):
            missing = set(self.agent_ids) - set(actions)
            extra = set(actions) - set(self.agent_ids)
            raise ValueError(f"actions must match agents; missing={sorted(missing)} extra={sorted(extra)}")

        previous_distance = self._total_distance()
        for agent_id, action in actions.items():
            if action not in {-1, 0, 1}:
                raise ValueError(f"invalid action for {agent_id}: {action}")
            self.positions[agent_id] = min(self.length - 1, max(0, self.positions[agent_id] + action))

        self.step_count += 1
        current_distance = self._total_distance()
        success = all(self.positions[agent_id] == self.targets[agent_id] for agent_id in self.agent_ids)
        done = success or self.step_count >= self.max_steps
        progress_reward = float(previous_distance - current_distance) * 0.2
        team_bonus = 1.0 if success else 0.0
        step_penalty = -0.01
        rewards = {agent_id: step_penalty + progress_reward + team_bonus for agent_id in self.agent_ids}
        return self._observations(), rewards, done, {
            "success": success,
            "step": self.step_count,
            "total_distance": current_distance,
        }

    def _observations(self) -> ObservationMap:
        peer_id = self.agent_ids[1] if len(self.agent_ids) > 1 else self.agent_ids[0]
        observations = {}
        for agent_id in self.agent_ids:
            other_id = next((candidate for candidate in self.agent_ids if candidate != agent_id), peer_id)
            observations[agent_id] = (
                self.positions[agent_id],
                self.targets[agent_id],
                self.positions[other_id],
                self.targets[other_id],
            )
        return observations

    def _total_distance(self) -> int:
        return sum(abs(self.positions[agent_id] - self.targets[agent_id]) for agent_id in self.agent_ids)
