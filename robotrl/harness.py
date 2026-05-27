from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from robotrl.agents.q_learning import QLearningAgent
from robotrl.envs.line_world import LineWorldEnv
from robotrl.envs.robot_arm import RobotArmReachEnv
from robotrl.video import render_robot_arm_rollout_gif


class TrainableEnv(Protocol):
    agent_ids: tuple[str, ...]

    def reset(self) -> dict[str, tuple[object, ...]]:
        ...

    def step(
        self,
        actions: dict[str, int],
    ) -> tuple[dict[str, tuple[object, ...]], dict[str, float], bool, dict[str, object]]:
        ...


@dataclass(frozen=True)
class TrainingConfig:
    env_name: str = "line_world"
    episodes: int = 100
    max_steps: int = 12
    seed: int = 0
    output_dir: Path = Path("runs/learning/run_next_line_world_seed0")
    agent_count: int = 2
    env_length: int = 7
    epsilon: float = 0.25
    epsilon_decay: float = 0.96
    epsilon_floor: float = 0.02


@dataclass(frozen=True)
class TrainingResult:
    metrics: dict[str, object]
    metrics_path: Path
    checkpoint_path: Path
    video_paths: tuple[Path, ...] = ()


def train(config: TrainingConfig) -> TrainingResult:
    if config.episodes < 1:
        raise ValueError("episodes must be positive")

    env = _make_env(config)
    agents = {
        agent_id: QLearningAgent(actions=(-1, 0, 1), epsilon=config.epsilon, seed=config.seed + index)
        for index, agent_id in enumerate(env.agent_ids)
    }
    milestones = _milestone_episodes(config.episodes)
    milestone_checkpoints: dict[str, dict[str, object]] = {}

    episode_summaries: list[dict[str, object]] = []
    for episode in range(1, config.episodes + 1):
        observations = env.reset()
        total_reward = {agent_id: 0.0 for agent_id in env.agent_ids}
        done = False
        info: dict[str, object] = {"success": False}

        while not done:
            actions = {
                agent_id: agents[agent_id].act(observations[agent_id])
                for agent_id in env.agent_ids
            }
            next_observations, rewards, done, info = env.step(actions)
            for agent_id in env.agent_ids:
                agents[agent_id].update(
                    observations[agent_id],
                    actions[agent_id],
                    rewards[agent_id],
                    next_observations[agent_id],
                    done,
                )
                total_reward[agent_id] += rewards[agent_id]
            observations = next_observations

        for agent in agents.values():
            agent.decay_epsilon(config.epsilon_decay, config.epsilon_floor)

        summary = {
            "episode": episode,
            "success": bool(info["success"]),
            "timeout": not bool(info["success"]),
            "steps": int(info["step"]),
            "team_reward": round(sum(total_reward.values()), 6),
        }
        for distance_key in ("total_distance", "joint_distance", "end_effector_distance"):
            if distance_key in info:
                summary[distance_key] = int(info[distance_key])
        episode_summaries.append(summary)
        if episode in milestones:
            milestone_checkpoints[milestones[episode]] = _checkpoint(config, env, agents)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = config.output_dir / "metrics.json"
    checkpoint_path = config.output_dir / "policy.json"
    metrics = _build_metrics(config, episode_summaries)
    checkpoint = _checkpoint(config, env, agents)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True), encoding="utf-8")
    video_paths = _write_milestone_artifacts(config, milestone_checkpoints)
    return TrainingResult(
        metrics=metrics,
        metrics_path=metrics_path,
        checkpoint_path=checkpoint_path,
        video_paths=video_paths,
    )


def _checkpoint(
    config: TrainingConfig,
    env: TrainableEnv,
    agents: dict[str, QLearningAgent],
) -> dict[str, object]:
    return {
        "env": _env_metadata(config, env),
        "agents": {agent_id: agent.snapshot() for agent_id, agent in agents.items()},
    }


def _milestone_episodes(episodes: int) -> dict[int, str]:
    return {
        1: "early",
        max(1, episodes // 2): "mid",
        episodes: "late",
    }


def _write_milestone_artifacts(
    config: TrainingConfig,
    milestone_checkpoints: dict[str, dict[str, object]],
) -> tuple[Path, ...]:
    if config.env_name != "robot_arm":
        return ()

    checkpoints_dir = config.output_dir / "checkpoints"
    videos_dir = config.output_dir / "videos"
    video_paths = []
    for name in ("early", "mid", "late"):
        checkpoint = milestone_checkpoints[name]
        checkpoint_path = checkpoints_dir / f"{name}_policy.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True), encoding="utf-8")
        video_paths.append(
            render_robot_arm_rollout_gif(
                checkpoint=checkpoint,
                output_path=videos_dir / f"{name}_rollout.gif",
                max_steps=config.max_steps,
                seed=config.seed,
            )
        )
    return tuple(video_paths)


def _make_env(config: TrainingConfig) -> TrainableEnv:
    if config.env_name == "line_world":
        return LineWorldEnv(
            length=config.env_length,
            max_steps=config.max_steps,
            agent_count=config.agent_count,
            seed=config.seed,
        )
    if config.env_name == "robot_arm":
        return RobotArmReachEnv(
            joint_bins=config.env_length,
            max_steps=config.max_steps,
            seed=config.seed,
        )
    raise ValueError(f"unknown env_name: {config.env_name}")


def _env_metadata(config: TrainingConfig, env: TrainableEnv) -> dict[str, object]:
    if isinstance(env, LineWorldEnv):
        return {
            "name": "LineWorldEnv",
            "length": config.env_length,
            "max_steps": config.max_steps,
            "agent_count": config.agent_count,
        }
    if isinstance(env, RobotArmReachEnv):
        return {
            "name": "RobotArmReachEnv",
            "joint_bins": config.env_length,
            "max_steps": config.max_steps,
            "target": list(env.target or ()),
        }
    raise TypeError(f"unsupported env type: {type(env).__name__}")


def _build_metrics(config: TrainingConfig, episode_summaries: list[dict[str, object]]) -> dict[str, object]:
    successes = [bool(row["success"]) for row in episode_summaries]
    last_10 = successes[-10:]
    metrics: dict[str, object] = {
        "env_name": config.env_name,
        "episodes": config.episodes,
        "agent_count": config.agent_count,
        "seed": config.seed,
        "timeout_count": sum(1 for row in episode_summaries if bool(row["timeout"])),
        "success_rate": round(sum(successes) / len(successes), 4),
        "success_rate_last_10": round(sum(last_10) / len(last_10), 4),
        "mean_steps_last_10": round(sum(int(row["steps"]) for row in episode_summaries[-10:]) / len(last_10), 2),
        "mean_team_reward_last_10": round(
            sum(float(row["team_reward"]) for row in episode_summaries[-10:]) / len(last_10),
            4,
        ),
        "episodes_detail": episode_summaries,
    }
    end_effector_distances = [
        int(row["end_effector_distance"])
        for row in episode_summaries[-10:]
        if "end_effector_distance" in row
    ]
    if end_effector_distances:
        metrics["mean_end_effector_distance_last_10"] = round(
            sum(end_effector_distances) / len(end_effector_distances),
            2,
        )
    return metrics
