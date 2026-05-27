from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable


State = tuple[object, ...]


@dataclass
class QLearningAgent:
    actions: tuple[int, ...]
    learning_rate: float = 0.3
    discount: float = 0.95
    epsilon: float = 0.15
    seed: int | None = None
    q_table: dict[tuple[State, int], float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def act(self, state: Iterable[object], *, explore: bool = True) -> int:
        state_key = tuple(state)
        if explore and self._rng.random() < self.epsilon:
            return self._rng.choice(self.actions)
        return max(self.actions, key=lambda action: (self.value(state_key, action), -abs(action), -action))

    def value(self, state: Iterable[object], action: int) -> float:
        return self.q_table.get((tuple(state), action), 0.0)

    def update(
        self,
        state: Iterable[object],
        action: int,
        reward: float,
        next_state: Iterable[object],
        done: bool,
    ) -> None:
        state_key = tuple(state)
        next_key = tuple(next_state)
        current = self.value(state_key, action)
        bootstrap = 0.0 if done else max(self.value(next_key, next_action) for next_action in self.actions)
        target = reward + self.discount * bootstrap
        self.q_table[(state_key, action)] = current + self.learning_rate * (target - current)

    def decay_epsilon(self, factor: float, floor: float) -> None:
        self.epsilon = max(floor, self.epsilon * factor)

    def snapshot(self) -> dict[str, object]:
        entries = [
            {"state": list(state), "action": action, "value": value}
            for (state, action), value in sorted(self.q_table.items(), key=lambda item: (item[0][0], item[0][1]))
        ]
        return {
            "actions": list(self.actions),
            "learning_rate": self.learning_rate,
            "discount": self.discount,
            "epsilon": self.epsilon,
            "seed": self.seed,
            "q_table": entries,
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, object]) -> "QLearningAgent":
        agent = cls(
            actions=tuple(int(action) for action in snapshot["actions"]),
            learning_rate=float(snapshot["learning_rate"]),
            discount=float(snapshot["discount"]),
            epsilon=float(snapshot["epsilon"]),
            seed=None if snapshot["seed"] is None else int(snapshot["seed"]),
        )
        for entry in snapshot["q_table"]:
            row = dict(entry)
            agent.q_table[(tuple(row["state"]), int(row["action"]))] = float(row["value"])
        return agent
