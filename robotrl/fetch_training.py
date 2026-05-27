from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import sys
import time
from dataclasses import dataclass
from itertools import count
from pathlib import Path

import numpy as np

from robotrl.fetch_envs import (
    FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
    FETCH_BOX_PLACE_DENSE_ENV_ID,
    FETCH_BOX_PLACE_ENV_ID,
    FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
    FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID,
    FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID,
    FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
    FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_BASIC_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
    register_robotrl_fetch_envs,
)


class FetchDependencyError(RuntimeError):
    pass


FETCH_MAX_EPISODE_STEPS = FETCH_BOX_PLACE_MAX_EPISODE_STEPS
VISUAL_APPROVAL_SCHEMA_VERSION = 1
VISUAL_APPROVAL_CRITERIA = (
    "approach",
    "stable_contact_or_grasp",
    "lift_or_carry",
    "collidable_box_placement",
    "home_return",
    "no_penetration_sliding_or_teleport",
)
VISUAL_MIN_INITIAL_OBJECT_GOAL_DISTANCE = 0.08
VISUAL_MIN_OBJECT_MOTION_DISTANCE = 0.05
VISUAL_MAX_GRIPPER_OBJECT_DISTANCE = 0.04
VISUAL_MIN_OBJECT_LIFT = 0.04
VISUAL_MAX_STEP_OBJECT_DISPLACEMENT = 0.12
VISUAL_MAX_NO_CONTACT_STEP_DISPLACEMENT = 0.04


@dataclass(frozen=True)
class FetchTrainingConfig:
    env_id: str = FETCH_BOX_PLACE_DENSE_ENV_ID
    total_timesteps: int = 2_000_000
    seed: int = 0
    output_dir: Path = Path("runs/learning/run_next_fetch_box_place_dense")
    n_envs: int = 6
    learning_starts: int = 10_000
    checkpoint_interval: int = 50_000
    batch_size: int = 256
    buffer_size: int = 1_000_000
    gamma: float = 0.95
    learning_rate: float = 0.001
    tensorboard_log: Path | None = None
    progress_bar: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class FetchTrainingResult:
    spec_path: Path
    model_path: Path | None = None
    checkpoint_dir: Path | None = None


@dataclass(frozen=True)
class FetchLoopConfig:
    env_id: str = FETCH_BOX_PLACE_DENSE_ENV_ID
    curriculum_stage_env_ids: tuple[str, ...] = ()
    chunk_timesteps: int = 50_000
    seed: int = 7
    output_dir: Path = Path("runs/learning/run_next_fetch_box_place_dense_loop_seed7")
    n_envs: int = 6
    learning_starts: int = 10_000
    checkpoint_interval: int = 50_000
    batch_size: int = 256
    buffer_size: int = 1_000_000
    gamma: float = 0.95
    learning_rate: float = 0.001
    eval_episodes: int = 20
    success_threshold: float = 0.8
    max_iterations: int | None = None
    resume_from: Path | None = None
    progress_bar: bool = False
    dry_run: bool = False
    visual_approval_required: bool = False
    visual_approval_timeout_seconds: float = 300.0
    visual_approval_poll_interval_seconds: float = 5.0


@dataclass(frozen=True)
class FetchLoopResult:
    spec_path: Path
    eval_path: Path
    model_path: Path | None = None
    video_path: Path | None = None
    success: bool = False


def build_fetch_training_spec(config: FetchTrainingConfig) -> dict[str, object]:
    return {
        "env_id": config.env_id,
        "algorithm": "SAC",
        "policy": "MultiInputPolicy",
        "replay_buffer": _replay_buffer_name(config.env_id),
        "total_timesteps": config.total_timesteps,
        "seed": config.seed,
        "n_envs": config.n_envs,
        "learning_starts": config.learning_starts,
        "checkpoint_interval": config.checkpoint_interval,
        "batch_size": config.batch_size,
        "buffer_size": config.buffer_size,
        "gamma": config.gamma,
        "learning_rate": config.learning_rate,
        "progress_bar": config.progress_bar,
    }


def build_fetch_loop_spec(config: FetchLoopConfig) -> dict[str, object]:
    stage_env_ids = curriculum_stage_env_ids(config)
    return {
        "env_id": config.env_id,
        "curriculum_stage_env_ids": list(stage_env_ids),
        "initial_stage_index": 0,
        "initial_stage_env_id": stage_env_ids[0],
        "final_stage_env_id": stage_env_ids[-1],
        "algorithm": "SAC",
        "policy": "MultiInputPolicy",
        "replay_buffer": _replay_buffer_name(config.env_id),
        "chunk_timesteps": config.chunk_timesteps,
        "seed": config.seed,
        "n_envs": config.n_envs,
        "learning_starts": config.learning_starts,
        "checkpoint_interval": config.checkpoint_interval,
        "batch_size": config.batch_size,
        "buffer_size": config.buffer_size,
        "gamma": config.gamma,
        "learning_rate": config.learning_rate,
        "eval_episodes": config.eval_episodes,
        "success_threshold": config.success_threshold,
        "max_iterations": config.max_iterations,
        "resume_from": None if config.resume_from is None else str(config.resume_from),
        "progress_bar": config.progress_bar,
        "visual_approval_required": config.visual_approval_required,
        "visual_approval_timeout_seconds": config.visual_approval_timeout_seconds,
        "visual_approval_poll_interval_seconds": config.visual_approval_poll_interval_seconds,
        "continue_until_success": config.max_iterations is None,
    }


def is_success_condition_met(eval_record: dict[str, object], *, video_path: Path, threshold: float) -> bool:
    success_rate = float(eval_record["success_rate"])
    success_requires_valid_box_entry_value = eval_record.get("success_requires_valid_box_entry_rate", 1.0)
    if success_requires_valid_box_entry_value is None:
        success_requires_valid_box_entry_value = 1.0
    success_requires_valid_box_entry = float(success_requires_valid_box_entry_value) >= 0.5
    required_object_names = eval_record.get("required_object_names")
    if success_requires_valid_box_entry:
        if required_object_names:
            required_entry_keys = [
                f"{object_name}_valid_box_entry_rate"
                for object_name in required_object_names
            ]
        else:
            required_entry_keys = [
                key
                for key in eval_record
                if key.endswith("_valid_box_entry_rate")
            ]
        physical_entry_rates = [
            eval_record.get(key)
            for key in required_entry_keys
            if eval_record.get(key) is not None
        ]
        if physical_entry_rates and any(float(value) < success_rate for value in physical_entry_rates):
            return False
    if not (
        success_rate >= threshold
        and int(eval_record["episodes"]) > 0
        and video_path.exists()
        and video_path.stat().st_size > 0
    ):
        return False
    if bool(eval_record.get("visual_approval_required", False)):
        if not _visual_trajectory_gate(eval_record):
            return False
        marker_value = eval_record.get("visual_approval_marker")
        marker_path = Path(str(marker_value)) if marker_value else _visual_approval_marker_path(video_path)
        if not marker_path.exists():
            return False
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        if not _visual_approval_marker_is_valid(marker, video_path=video_path, eval_record=eval_record):
            return False
    return True


def _visual_approval_marker_path(video_path: Path) -> Path:
    return video_path.with_suffix(".approved.json")


def _visual_approval_marker_is_valid(marker: object, *, video_path: Path, eval_record: dict[str, object]) -> bool:
    if not isinstance(marker, dict):
        return False
    if marker.get("schema_version") != VISUAL_APPROVAL_SCHEMA_VERSION:
        return False
    if marker.get("approved") is not True:
        return False
    if not str(marker.get("reviewer", "")).strip():
        return False
    if not str(marker.get("tool", "")).strip():
        return False
    if str(marker.get("reviewed_gif_path", "")) != str(video_path):
        return False
    expected_hash = eval_record.get("visual_artifact_sha256")
    if expected_hash is not None and marker.get("artifact_sha256") != str(expected_hash):
        return False
    if marker.get("artifact_sha256") != _file_sha256(video_path):
        return False
    criteria = marker.get("criteria")
    if not isinstance(criteria, dict):
        return False
    for criterion in VISUAL_APPROVAL_CRITERIA:
        result = criteria.get(criterion)
        if not isinstance(result, dict):
            return False
        if criterion == "home_return" and not _return_home_required(eval_record):
            if not isinstance(result.get("passed"), bool):
                return False
            if result.get("passed") is False and result.get("required") is not False:
                return False
            continue
        if result.get("passed") is not True:
            return False
    return True


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _visual_trajectory_gate(eval_record: dict[str, object]) -> bool:
    checks = (
        ("video_initial_object_goal_distance", VISUAL_MIN_INITIAL_OBJECT_GOAL_DISTANCE, "min"),
        ("video_object_motion_distance", VISUAL_MIN_OBJECT_MOTION_DISTANCE, "min"),
        ("video_min_gripper_object_distance", VISUAL_MAX_GRIPPER_OBJECT_DISTANCE, "max"),
        ("video_max_object_lift", VISUAL_MIN_OBJECT_LIFT, "min"),
        ("video_max_step_object_displacement", VISUAL_MAX_STEP_OBJECT_DISPLACEMENT, "max"),
        (
            "video_max_step_object_displacement_without_contact",
            VISUAL_MAX_NO_CONTACT_STEP_DISPLACEMENT,
            "max",
        ),
    )
    for key, threshold, mode in checks:
        value = eval_record.get(key)
        if value is None:
            return False
        numeric_value = float(value)
        if mode == "min" and numeric_value < threshold:
            return False
        if mode == "max" and numeric_value > threshold:
            return False
    if float(eval_record.get("video_episode_success", 0.0)) < 1.0:
        return False
    if _return_home_required(eval_record) and float(eval_record.get("video_place_return_success", 0.0)) < 1.0:
        return False
    return True


def _return_home_required(eval_record: dict[str, object]) -> bool:
    stage_env_id = str(eval_record.get("curriculum_stage_env_id", ""))
    if "ReturnHome" in stage_env_id:
        return True
    if eval_record.get("place_return_success_rate") is not None:
        return bool(eval_record.get("visual_require_home_return", False))
    return False


def _wait_for_visual_approval(
    eval_record: dict[str, object],
    *,
    video_path: Path,
    threshold: float,
    timeout_seconds: float,
    poll_interval_seconds: float,
    monotonic: object = time.monotonic,
    sleep: object = time.sleep,
) -> bool:
    eval_record["visual_approval_status"] = "pending"
    if not _visual_ready_for_approval(eval_record, video_path=video_path, threshold=threshold):
        eval_record["visual_approval_status"] = "not_ready"
        return False
    eval_record.setdefault("visual_artifact_sha256", _file_sha256(video_path))
    deadline = float(monotonic()) + max(0.0, float(timeout_seconds))
    poll_interval = max(0.0, float(poll_interval_seconds))
    while True:
        if is_success_condition_met(eval_record, video_path=video_path, threshold=threshold):
            eval_record["visual_approval_status"] = "approved"
            return True
        if float(monotonic()) >= deadline:
            eval_record["visual_approval_status"] = "pending"
            return False
        sleep(min(poll_interval, max(0.0, deadline - float(monotonic()))))


def _visual_ready_for_approval(eval_record: dict[str, object], *, video_path: Path, threshold: float) -> bool:
    if not bool(eval_record.get("visual_approval_required", False)):
        return False
    visual_required = dict(eval_record)
    visual_required["visual_approval_required"] = False
    return (
        is_success_condition_met(visual_required, video_path=video_path, threshold=threshold)
        and _visual_trajectory_gate(eval_record)
    )


def curriculum_stage_env_ids(config: FetchLoopConfig) -> tuple[str, ...]:
    if config.curriculum_stage_env_ids:
        return config.curriculum_stage_env_ids
    return (config.env_id,)


def curriculum_stage_decision(*, stage_index: int, stage_count: int, stage_success: bool) -> str:
    if not stage_success:
        return "continue"
    if stage_index < stage_count - 1:
        return "advance"
    return "complete"


def train_fetch(config: FetchTrainingConfig) -> FetchTrainingResult:
    if config.total_timesteps < 1:
        raise ValueError("total_timesteps must be positive")
    if config.n_envs < 1:
        raise ValueError("n_envs must be positive")
    _validate_fetch_learning_starts(config.learning_starts, n_envs=config.n_envs)
    if config.checkpoint_interval < 1:
        raise ValueError("checkpoint_interval must be positive")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    spec_path = config.output_dir / "fetch_training_spec.json"
    spec_path.write_text(json.dumps(build_fetch_training_spec(config), indent=2, sort_keys=True), encoding="utf-8")
    if config.dry_run:
        return FetchTrainingResult(spec_path=spec_path)

    _require_fetch_dependencies()
    return _train_fetch_with_dependencies(config, spec_path)


def run_fetch_loop(config: FetchLoopConfig) -> FetchLoopResult:
    if config.chunk_timesteps < 1:
        raise ValueError("chunk_timesteps must be positive")
    if config.n_envs < 1:
        raise ValueError("n_envs must be positive")
    _validate_fetch_learning_starts(config.learning_starts, n_envs=config.n_envs)
    if not 0.0 <= config.success_threshold <= 1.0:
        raise ValueError("success_threshold must be between 0 and 1")
    if config.eval_episodes < 1:
        raise ValueError("eval_episodes must be positive")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    spec_path = config.output_dir / "fetch_loop_spec.json"
    eval_path = config.output_dir / "eval_results.json"
    spec_path.write_text(json.dumps(build_fetch_loop_spec(config), indent=2, sort_keys=True), encoding="utf-8")
    if config.dry_run:
        if not eval_path.exists():
            eval_path.write_text("[]\n", encoding="utf-8")
        return FetchLoopResult(spec_path=spec_path, eval_path=eval_path)

    _require_fetch_dependencies()
    return _run_fetch_loop_with_dependencies(config, spec_path, eval_path)


def _validate_fetch_learning_starts(learning_starts: int, *, n_envs: int) -> None:
    minimum_learning_starts = FETCH_MAX_EPISODE_STEPS * n_envs
    if learning_starts <= minimum_learning_starts:
        raise ValueError(
            "learning_starts must be greater than Fetch max episode length "
            f"times n_envs ({minimum_learning_starts}) for HER replay sampling"
        )


def _uses_her_replay_buffer(env_id: str) -> bool:
    return env_id not in {
        FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
        FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
        FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
        FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
        FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID,
        FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID,
        FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
        FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
    }


def _replay_buffer_name(env_id: str) -> str:
    if _uses_her_replay_buffer(env_id):
        return "HerReplayBuffer"
    return "DictReplayBuffer"


def select_fetch_vec_env_name(*, env_id: str, n_envs: int, platform_name: str = sys.platform) -> str:
    if n_envs == 1:
        return "DummyVecEnv"
    if platform_name == "win32" and env_id in {
        FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
        FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
        FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
        FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
        FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID,
        FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID,
        FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
        FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
        FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
    }:
        return "DummyVecEnv"
    return "SubprocVecEnv"


def _sac_model_kwargs(
    *,
    policy: str,
    env: object,
    her_replay_buffer_class: object,
    env_id: str,
    learning_starts: int,
    batch_size: int,
    buffer_size: int,
    gamma: float,
    learning_rate: float,
    tensorboard_log: str,
    seed: int,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "policy": policy,
        "env": env,
        "learning_starts": learning_starts,
        "batch_size": batch_size,
        "buffer_size": buffer_size,
        "gamma": gamma,
        "learning_rate": learning_rate,
        "tensorboard_log": tensorboard_log,
        "seed": seed,
        "verbose": 1,
    }
    if _uses_her_replay_buffer(env_id):
        kwargs["replay_buffer_class"] = her_replay_buffer_class
    return kwargs


def _require_fetch_dependencies() -> None:
    missing = [
        module
        for module in ("gymnasium", "gymnasium_robotics", "mujoco", "stable_baselines3")
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        raise FetchDependencyError(
            "Fetch training requires missing packages: "
            + ", ".join(missing)
            + ". Install the Fetch extras first, then rerun fetch-train."
        )


def _train_fetch_with_dependencies(config: FetchTrainingConfig, spec_path: Path) -> FetchTrainingResult:
    import gymnasium_robotics  # noqa: F401
    from stable_baselines3 import HerReplayBuffer, SAC
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    register_robotrl_fetch_envs()

    class TimestepCheckpointCallback(BaseCallback):
        def __init__(self, *, checkpoint_dir: Path, env_id: str, interval: int) -> None:
            super().__init__()
            self.checkpoint_dir = checkpoint_dir
            self.env_id = env_id.replace("-", "_")
            self.interval = interval
            self.next_timestep = interval

        def _on_step(self) -> bool:
            while self.num_timesteps >= self.next_timestep:
                path = self.checkpoint_dir / f"{self.env_id}_sac_{self.next_timestep}_steps"
                self.model.save(path)
                self.next_timestep += self.interval
            return True

    checkpoint_dir = config.output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    tensorboard_log = config.tensorboard_log or (config.output_dir / "tensorboard")
    env = _make_fetch_vec_env(
        env_id=config.env_id,
        n_envs=config.n_envs,
        seed=config.seed,
        dummy_vec_cls=DummyVecEnv,
        subproc_vec_cls=SubprocVecEnv,
    )
    model = SAC(
        **_sac_model_kwargs(
            policy="MultiInputPolicy",
            env=env,
            her_replay_buffer_class=HerReplayBuffer,
            env_id=config.env_id,
            learning_starts=config.learning_starts,
            batch_size=config.batch_size,
            buffer_size=config.buffer_size,
            gamma=config.gamma,
            learning_rate=config.learning_rate,
            tensorboard_log=str(tensorboard_log),
            seed=config.seed,
        ),
    )
    callback = TimestepCheckpointCallback(
        checkpoint_dir=checkpoint_dir,
        env_id=config.env_id,
        interval=config.checkpoint_interval,
    )
    model.learn(
        total_timesteps=config.total_timesteps,
        callback=callback,
        progress_bar=config.progress_bar,
    )
    model_path = config.output_dir / "final_model.zip"
    model.save(model_path)
    env.close()
    return FetchTrainingResult(spec_path=spec_path, model_path=model_path, checkpoint_dir=checkpoint_dir)


def _run_fetch_loop_with_dependencies(config: FetchLoopConfig, spec_path: Path, eval_path: Path) -> FetchLoopResult:
    import gymnasium as gym
    import gymnasium_robotics  # noqa: F401
    import imageio.v2 as imageio
    from stable_baselines3 import HerReplayBuffer, SAC
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    register_robotrl_fetch_envs()

    class TimestepCheckpointCallback(BaseCallback):
        def __init__(self, *, checkpoint_dir: Path, env_id: str, interval: int) -> None:
            super().__init__()
            self.checkpoint_dir = checkpoint_dir
            self.env_id = env_id.replace("-", "_")
            self.interval = interval
            self.next_timestep = interval

        def _on_step(self) -> bool:
            while self.num_timesteps >= self.next_timestep:
                path = self.checkpoint_dir / f"{self.env_id}_sac_{self.next_timestep}_steps"
                self.model.save(path)
                self.next_timestep += self.interval
            return True

    checkpoint_dir = config.output_dir / "checkpoints"
    videos_dir = config.output_dir / "videos"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)
    eval_records = _read_eval_records(eval_path)

    stage_env_ids = curriculum_stage_env_ids(config)
    stage_index = 0
    current_env_id = stage_env_ids[stage_index]

    env = _make_fetch_vec_env(
        env_id=current_env_id,
        n_envs=config.n_envs,
        seed=config.seed,
        dummy_vec_cls=DummyVecEnv,
        subproc_vec_cls=SubprocVecEnv,
    )
    if config.resume_from is not None:
        model = SAC.load(
            str(config.resume_from),
            env=env,
            tensorboard_log=str(config.output_dir / "tensorboard"),
        )
    else:
        model = SAC(
            **_sac_model_kwargs(
                policy="MultiInputPolicy",
                env=env,
                her_replay_buffer_class=HerReplayBuffer,
                env_id=current_env_id,
                learning_starts=config.learning_starts,
                batch_size=config.batch_size,
                buffer_size=config.buffer_size,
                gamma=config.gamma,
                learning_rate=config.learning_rate,
                tensorboard_log=str(config.output_dir / "tensorboard"),
                seed=config.seed,
            ),
        )
    callback = TimestepCheckpointCallback(
        checkpoint_dir=checkpoint_dir,
        env_id=current_env_id,
        interval=config.checkpoint_interval,
    )

    last_model_path: Path | None = None
    last_video_path: Path | None = None
    try:
        for iteration in count(1):
            if config.max_iterations is not None and iteration > config.max_iterations:
                break
            model.learn(
                total_timesteps=config.chunk_timesteps,
                callback=callback,
                reset_num_timesteps=False,
                progress_bar=config.progress_bar,
            )
            last_model_path = config.output_dir / "latest_model.zip"
            iteration_model_path = checkpoint_dir / f"stage_{stage_index + 1:02d}_iteration_{iteration:03d}_model.zip"
            model.save(last_model_path)
            model.save(iteration_model_path)
            last_video_path = videos_dir / f"stage_{stage_index + 1:02d}_iteration_{iteration:03d}_rollout.gif"
            eval_record = _evaluate_fetch_model(
                gym=gym,
                imageio=imageio,
                model=model,
                env_id=current_env_id,
                seed=config.seed + iteration,
                episodes=config.eval_episodes,
                iteration=iteration,
                total_timesteps=int(model.num_timesteps),
                video_path=last_video_path,
            )
            eval_record["curriculum_stage_index"] = stage_index
            eval_record["curriculum_stage_count"] = len(stage_env_ids)
            eval_record["curriculum_stage_env_id"] = current_env_id
            eval_record["visual_approval_required"] = config.visual_approval_required
            if config.visual_approval_required:
                eval_record["visual_approval_marker"] = str(_visual_approval_marker_path(last_video_path))
                eval_record["visual_artifact_sha256"] = _file_sha256(last_video_path)
                eval_record["visual_approval_status"] = "pending"
            eval_records.append(eval_record)
            _write_eval_records(eval_path, eval_records)
            if config.visual_approval_required and _visual_ready_for_approval(
                eval_record,
                video_path=last_video_path,
                threshold=config.success_threshold,
            ):
                _wait_for_visual_approval(
                    eval_record,
                    video_path=last_video_path,
                    threshold=config.success_threshold,
                    timeout_seconds=config.visual_approval_timeout_seconds,
                    poll_interval_seconds=config.visual_approval_poll_interval_seconds,
                )
                _write_eval_records(eval_path, eval_records)
            stage_success = is_success_condition_met(
                eval_record,
                video_path=last_video_path,
                threshold=config.success_threshold,
            )
            decision = curriculum_stage_decision(
                stage_index=stage_index,
                stage_count=len(stage_env_ids),
                stage_success=stage_success,
            )
            if decision == "advance":
                stage_model_path = checkpoint_dir / f"stage_{stage_index + 1:02d}_complete_model.zip"
                model.save(stage_model_path)
                env.close()
                stage_index += 1
                current_env_id = stage_env_ids[stage_index]
                callback.env_id = current_env_id.replace("-", "_")
                env = _make_fetch_vec_env(
                    env_id=current_env_id,
                    n_envs=config.n_envs,
                    seed=config.seed + stage_index,
                    dummy_vec_cls=DummyVecEnv,
                    subproc_vec_cls=SubprocVecEnv,
                )
                model.set_env(env)
                continue
            if decision == "complete":
                success_model_path = config.output_dir / "success_model.zip"
                shutil.copyfile(last_model_path, success_model_path)
                return FetchLoopResult(
                    spec_path=spec_path,
                    eval_path=eval_path,
                    model_path=success_model_path,
                    video_path=last_video_path,
                    success=True,
                )
    finally:
        env.close()

    return FetchLoopResult(
        spec_path=spec_path,
        eval_path=eval_path,
        model_path=last_model_path,
        video_path=last_video_path,
        success=False,
    )


def _evaluate_fetch_model(
    *,
    gym: object,
    imageio: object,
    model: object,
    env_id: str,
    seed: int,
    episodes: int,
    iteration: int,
    total_timesteps: int,
    video_path: Path,
) -> dict[str, object]:
    successes = []
    rewards = []
    final_object_goal_distances = []
    min_gripper_object_distances = []
    max_object_lifts = []
    home_distances = []
    return_home_successes = []
    place_return_successes = []
    object_counts = []
    objects_in_box_counts = []
    object0_in_box_successes = []
    object1_in_box_successes = []
    all_objects_in_box_successes = []
    multi_place_return_successes = []
    valid_box_entry_counts = []
    object0_valid_box_entries = []
    object1_valid_box_entries = []
    success_requires_valid_box_entries = []
    required_object_names: list[str] | None = None
    video_frames = []
    video_episode_index: int | None = None
    video_episode_success = 0.0
    video_initial_object_goal_distance: float | None = None
    video_object_motion_distance: float | None = None
    video_min_gripper_object_distance: float | None = None
    video_max_object_lift: float | None = None
    video_max_step_object_displacement: float | None = None
    video_max_step_object_displacement_without_contact: float | None = None
    video_place_return_success: float | None = None
    video_return_home_success: float | None = None
    successful_video_recorded = False
    for episode in range(episodes):
        render_mode = "rgb_array" if not successful_video_recorded else None
        register_robotrl_fetch_envs()
        env = gym.make(env_id, render_mode=render_mode)
        obs, _info = env.reset(seed=seed + episode)
        done = False
        total_reward = 0.0
        final_info: dict[str, object] = {}
        min_gripper_object_distance = float("inf")
        max_object_lift = 0.0
        episode_frames = []
        initial_object_goal_distance = _initial_object_goal_distance(obs)
        initial_object_position = _achieved_goal_array(obs)
        previous_object_position = initial_object_position
        max_object_motion_distance = 0.0
        max_step_object_displacement = 0.0
        max_step_object_displacement_without_contact = 0.0
        if render_mode:
            episode_frames.append(env.render())
        while not done:
            action, _state = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = bool(terminated or truncated)
            total_reward += float(reward)
            final_info = dict(info)
            if "gripper_object_distance" in final_info:
                min_gripper_object_distance = min(
                    min_gripper_object_distance,
                    float(final_info["gripper_object_distance"]),
                )
            if "object_lift" in final_info:
                max_object_lift = max(max_object_lift, float(final_info["object_lift"]))
            object_position = _achieved_goal_array(obs)
            if initial_object_position is not None and object_position is not None:
                max_object_motion_distance = max(
                    max_object_motion_distance,
                    float(np.linalg.norm(object_position - initial_object_position)),
                )
            if previous_object_position is not None and object_position is not None:
                step_displacement = float(np.linalg.norm(object_position - previous_object_position))
                max_step_object_displacement = max(max_step_object_displacement, step_displacement)
                gripper_distance = final_info.get("gripper_object_distance")
                if gripper_distance is None or float(gripper_distance) > VISUAL_MAX_GRIPPER_OBJECT_DISTANCE:
                    max_step_object_displacement_without_contact = max(
                        max_step_object_displacement_without_contact,
                        step_displacement,
                    )
            previous_object_position = object_position
            if render_mode:
                episode_frames.append(env.render())
        env.close()
        episode_success = float(final_info.get("is_success", 0.0))
        if render_mode and (not video_frames or episode_success >= 1.0):
            video_frames = episode_frames
            video_episode_index = episode
            video_episode_success = episode_success
            video_initial_object_goal_distance = initial_object_goal_distance
            video_object_motion_distance = max_object_motion_distance
            video_min_gripper_object_distance = (
                None
                if min_gripper_object_distance == float("inf")
                else min_gripper_object_distance
            )
            video_max_object_lift = max_object_lift
            video_max_step_object_displacement = max_step_object_displacement
            video_max_step_object_displacement_without_contact = max_step_object_displacement_without_contact
            video_place_return_success = _optional_float(final_info.get("place_return_success"))
            video_return_home_success = _optional_float(final_info.get("return_home_success"))
            if episode_success >= 1.0:
                successful_video_recorded = True
        successes.append(episode_success)
        rewards.append(total_reward)
        if "object_goal_distance" in final_info:
            final_object_goal_distances.append(float(final_info["object_goal_distance"]))
        if "home_distance" in final_info:
            home_distances.append(float(final_info["home_distance"]))
        if "return_home_success" in final_info:
            return_home_successes.append(float(final_info["return_home_success"]))
        if "place_return_success" in final_info:
            place_return_successes.append(float(final_info["place_return_success"]))
        if "object_count" in final_info:
            object_counts.append(float(final_info["object_count"]))
        if "objects_in_box_count" in final_info:
            objects_in_box_counts.append(float(final_info["objects_in_box_count"]))
        if "object0_in_box" in final_info:
            object0_in_box_successes.append(float(final_info["object0_in_box"]))
        if "object1_in_box" in final_info:
            object1_in_box_successes.append(float(final_info["object1_in_box"]))
        if "all_objects_in_box" in final_info:
            all_objects_in_box_successes.append(float(final_info["all_objects_in_box"]))
        if "multi_place_return_success" in final_info:
            multi_place_return_successes.append(float(final_info["multi_place_return_success"]))
        if "valid_box_entry_count" in final_info:
            valid_box_entry_counts.append(float(final_info["valid_box_entry_count"]))
        if "object0_valid_box_entry" in final_info:
            object0_valid_box_entries.append(float(final_info["object0_valid_box_entry"]))
        if "object1_valid_box_entry" in final_info:
            object1_valid_box_entries.append(float(final_info["object1_valid_box_entry"]))
        if "success_requires_valid_box_entry" in final_info:
            success_requires_valid_box_entries.append(float(final_info["success_requires_valid_box_entry"]))
        if required_object_names is None and "object0_required" in final_info:
            required_object_names = [
                object_name
                for object_name in ("object0", "object1")
                if float(final_info.get(f"{object_name}_required", 0.0)) >= 1.0
            ]
        if min_gripper_object_distance != float("inf"):
            min_gripper_object_distances.append(min_gripper_object_distance)
        max_object_lifts.append(max_object_lift)

    video_path.parent.mkdir(parents=True, exist_ok=True)
    if video_frames:
        imageio.mimsave(video_path, video_frames, duration=120, loop=0)
    return {
        "iteration": iteration,
        "total_timesteps": total_timesteps,
        "episodes": episodes,
        "success_rate": round(sum(successes) / len(successes), 4),
        "mean_reward": round(sum(rewards) / len(rewards), 4),
        "mean_final_object_goal_distance": _rounded_mean(final_object_goal_distances),
        "mean_min_gripper_object_distance": _rounded_mean(min_gripper_object_distances),
        "mean_max_object_lift": _rounded_mean(max_object_lifts),
        "mean_home_distance": _rounded_mean(home_distances),
        "return_home_success_rate": _rounded_mean(return_home_successes),
        "place_return_success_rate": _rounded_mean(place_return_successes),
        "object_count": int(max(object_counts)) if object_counts else None,
        "mean_objects_in_box_count": _rounded_mean(objects_in_box_counts),
        "object0_in_box_rate": _rounded_mean(object0_in_box_successes),
        "object1_in_box_rate": _rounded_mean(object1_in_box_successes),
        "all_objects_in_box_rate": _rounded_mean(all_objects_in_box_successes),
        "multi_place_return_success_rate": _rounded_mean(multi_place_return_successes),
        "mean_valid_box_entry_count": _rounded_mean(valid_box_entry_counts),
        "object0_valid_box_entry_rate": _rounded_mean(object0_valid_box_entries),
        "object1_valid_box_entry_rate": _rounded_mean(object1_valid_box_entries),
        "success_requires_valid_box_entry_rate": _rounded_mean(success_requires_valid_box_entries),
        "required_object_names": required_object_names,
        "video_episode_index": video_episode_index,
        "video_episode_success": video_episode_success,
        "video_initial_object_goal_distance": (
            None
            if video_initial_object_goal_distance is None
            else round(video_initial_object_goal_distance, 4)
        ),
        "video_object_motion_distance": _rounded_optional(video_object_motion_distance),
        "video_min_gripper_object_distance": _rounded_optional(video_min_gripper_object_distance),
        "video_max_object_lift": _rounded_optional(video_max_object_lift),
        "video_max_step_object_displacement": _rounded_optional(video_max_step_object_displacement),
        "video_max_step_object_displacement_without_contact": _rounded_optional(
            video_max_step_object_displacement_without_contact
        ),
        "video_place_return_success": video_place_return_success,
        "video_return_home_success": video_return_home_success,
        "video": str(video_path),
    }


def _initial_object_goal_distance(obs: dict[str, object]) -> float | None:
    achieved_goal = obs.get("achieved_goal")
    desired_goal = obs.get("desired_goal")
    if achieved_goal is None or desired_goal is None:
        return None
    return float(np.linalg.norm(np.asarray(achieved_goal) - np.asarray(desired_goal)))


def _achieved_goal_array(obs: dict[str, object]) -> np.ndarray | None:
    achieved_goal = obs.get("achieved_goal")
    if achieved_goal is None:
        return None
    return np.asarray(achieved_goal, dtype=np.float64)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _rounded_optional(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _rounded_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _read_eval_records(eval_path: Path) -> list[dict[str, object]]:
    if not eval_path.exists():
        return []
    return list(json.loads(eval_path.read_text(encoding="utf-8")))


def _write_eval_records(eval_path: Path, records: list[dict[str, object]]) -> None:
    eval_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")


def _make_fetch_vec_env(
    *,
    env_id: str,
    n_envs: int,
    seed: int,
    dummy_vec_cls: object,
    subproc_vec_cls: object,
) -> object:
    env_fns = [_make_fetch_env_fn(env_id=env_id, seed=seed, rank=rank) for rank in range(n_envs)]
    vec_env_name = select_fetch_vec_env_name(env_id=env_id, n_envs=n_envs)
    if vec_env_name == "DummyVecEnv":
        return dummy_vec_cls(env_fns)
    return subproc_vec_cls(env_fns)


def _make_fetch_env_fn(*, env_id: str, seed: int, rank: int) -> object:
    def _init() -> object:
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(env_id)
        env.reset(seed=seed + rank)
        return env

    return _init
