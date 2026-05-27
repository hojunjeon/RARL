from __future__ import annotations

import random
from dataclasses import dataclass, field


ActionMap = dict[str, int]
ObservationMap = dict[str, tuple[int, int, int, int, int]]
RewardMap = dict[str, float]


@dataclass
class RobotArmReachEnv:
    joint_bins: int = 5
    max_steps: int = 10
    target: tuple[int, int] | None = None
    seed: int | None = None
    joints: dict[str, int] = field(init=False, default_factory=dict)
    step_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.joint_bins < 3:
            raise ValueError("joint_bins must be at least 3")
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")
        self._rng = random.Random(self.seed)
        self.agent_ids = ("shoulder", "elbow")
        if self.target is None:
            self.target = (self.joint_bins - 2, 1)
        if any(joint < 0 or joint >= self.joint_bins for joint in self.target):
            raise ValueError("target joints must fit inside joint_bins")

    def reset(self) -> ObservationMap:
        self.step_count = 0
        self.joints = {
            "shoulder": 0,
            "elbow": self.joint_bins // 2,
        }
        return self._observations()

    def step(self, actions: ActionMap) -> tuple[ObservationMap, RewardMap, bool, dict[str, object]]:
        if set(actions) != set(self.agent_ids):
            missing = set(self.agent_ids) - set(actions)
            extra = set(actions) - set(self.agent_ids)
            raise ValueError(f"actions must match agents; missing={sorted(missing)} extra={sorted(extra)}")

        previous_distance = self._joint_distance()
        for agent_id, action in actions.items():
            if action not in {-1, 0, 1}:
                raise ValueError(f"invalid action for {agent_id}: {action}")
            self.joints[agent_id] = min(self.joint_bins - 1, max(0, self.joints[agent_id] + action))

        self.step_count += 1
        current_distance = self._joint_distance()
        success = current_distance == 0
        done = success or self.step_count >= self.max_steps
        progress_reward = float(previous_distance - current_distance) * 0.25
        success_bonus = 1.0 if success else 0.0
        step_penalty = -0.01
        rewards = {agent_id: step_penalty + progress_reward + success_bonus for agent_id in self.agent_ids}
        return self._observations(), rewards, done, {
            "success": success,
            "step": self.step_count,
            "joint_distance": current_distance,
            "end_effector_distance": current_distance,
        }

    def _observations(self) -> ObservationMap:
        assert self.target is not None
        distance = self._joint_distance()
        shoulder = self.joints["shoulder"]
        elbow = self.joints["elbow"]
        target_shoulder, target_elbow = self.target
        return {
            "shoulder": (shoulder, elbow, target_shoulder, target_elbow, distance),
            "elbow": (elbow, shoulder, target_shoulder, target_elbow, distance),
        }

    def _joint_distance(self) -> int:
        assert self.target is not None
        return sum(abs(self.joints[agent_id] - self.target[index]) for index, agent_id in enumerate(self.agent_ids))
