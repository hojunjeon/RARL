from __future__ import annotations

import argparse
import re
from pathlib import Path

from robotrl.fetch_envs import (
    FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
    FETCH_BOX_PLACE_DENSE_ENV_ID,
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
)
from robotrl.fetch_training import (
    FetchDependencyError,
    FetchLoopConfig,
    FetchTrainingConfig,
    run_fetch_loop,
    train_fetch,
)
from robotrl.harness import TrainingConfig, train
from robotrl.improvement_loop import ImprovementLoopConfig, run_improvement_loop


def next_run_dir(label: str, *, root: Path = Path("runs/learning")) -> Path:
    highest = 0
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                match = re.match(r"run_(\d{3})_", child.name)
                if match:
                    highest = max(highest, int(match.group(1)))
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_").lower()
    return root / f"run_{highest + 1:03d}_{safe_label}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RobotRL multi-agent learning harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Train independent Q-learning agents in LineWorld.")
    train_parser.add_argument("--env", choices=("line_world", "robot_arm"), default="line_world")
    train_parser.add_argument("--episodes", type=int, default=100)
    train_parser.add_argument("--max-steps", type=int, default=12)
    train_parser.add_argument("--seed", type=int, default=0)
    train_parser.add_argument("--agent-count", type=int, default=2)
    train_parser.add_argument("--env-length", type=int, default=7)
    train_parser.add_argument("--output-dir", type=Path)

    fetch_parser = subparsers.add_parser("fetch-train", help="Train SAC+HER on a Gymnasium-Robotics Fetch task.")
    fetch_parser.add_argument("--env-id", default=FETCH_BOX_PLACE_DENSE_ENV_ID)
    fetch_parser.add_argument("--total-timesteps", type=int, default=2_000_000)
    fetch_parser.add_argument("--seed", type=int, default=0)
    fetch_parser.add_argument("--output-dir", type=Path)
    fetch_parser.add_argument("--n-envs", type=int, default=6)
    fetch_parser.add_argument("--learning-starts", type=int, default=10_000)
    fetch_parser.add_argument("--checkpoint-interval", type=int, default=50_000)
    fetch_parser.add_argument("--dry-run", action="store_true")

    loop_parser = subparsers.add_parser(
        "fetch-loop",
        help="Keep training, evaluating, and recording Fetch rollouts until the success gate is met.",
    )
    loop_parser.add_argument("--env-id", default=FETCH_BOX_PLACE_DENSE_ENV_ID)
    loop_parser.add_argument("--chunk-timesteps", type=int, default=50_000)
    loop_parser.add_argument("--seed", type=int, default=7)
    loop_parser.add_argument("--output-dir", type=Path)
    loop_parser.add_argument("--n-envs", type=int, default=6)
    loop_parser.add_argument("--learning-starts", type=int, default=10_000)
    loop_parser.add_argument("--checkpoint-interval", type=int, default=50_000)
    loop_parser.add_argument("--eval-episodes", type=int, default=20)
    loop_parser.add_argument("--success-threshold", type=float, default=0.8)
    loop_parser.add_argument("--max-iterations", type=int, default=None)
    loop_parser.add_argument(
        "--curriculum",
        choices=(
            "none",
            "basic-to-final",
            "final-to-return",
            "basic-to-final-return",
            "single-random-to-return",
            "two-to-two-return",
            "two-over-wall-return",
        ),
        default="none",
    )
    loop_parser.add_argument("--resume-from", type=Path)
    loop_parser.add_argument("--dry-run", action="store_true")
    loop_parser.add_argument("--visual-approval-timeout-seconds", type=float, default=300.0)
    loop_parser.add_argument("--visual-approval-poll-interval-seconds", type=float, default=5.0)

    improve_parser = subparsers.add_parser(
        "improve-loop",
        help="Run the deterministic planner/implementer/judge improvement loop harness.",
    )
    improve_parser.add_argument("--output-dir", type=Path)
    improve_parser.add_argument("--handoff-log-path", type=Path, default=Path("docs/recording_handoff_log.md"))
    improve_parser.add_argument("--max-iterations", type=int, default=4)
    improve_parser.add_argument("--max-call-attempts", type=int, default=3)
    improve_parser.add_argument("--initial-score", type=int, default=20)
    improve_parser.add_argument("--target-score", type=int, default=80)
    improve_parser.add_argument("--simulated-gain", type=int, default=15)
    improve_parser.add_argument("--fail-first-planner-call", action="store_true")

    args = parser.parse_args()
    if args.command == "train":
        result = train(
            TrainingConfig(
                env_name=args.env,
                episodes=args.episodes,
                max_steps=args.max_steps,
                seed=args.seed,
                output_dir=args.output_dir or next_run_dir(f"{args.env}_seed{args.seed}"),
                agent_count=args.agent_count,
                env_length=args.env_length,
            )
        )
        print(f"metrics={result.metrics_path}")
        print(f"checkpoint={result.checkpoint_path}")
        print(f"success_rate_last_10={result.metrics['success_rate_last_10']}")
    elif args.command == "fetch-train":
        try:
            result = train_fetch(
                FetchTrainingConfig(
                    env_id=args.env_id,
                    total_timesteps=args.total_timesteps,
                    seed=args.seed,
                    output_dir=args.output_dir or next_run_dir(f"fetch_train_{args.env_id}_seed{args.seed}"),
                    n_envs=args.n_envs,
                    learning_starts=args.learning_starts,
                    checkpoint_interval=args.checkpoint_interval,
                    dry_run=args.dry_run,
                )
            )
        except FetchDependencyError as exc:
            parser.error(str(exc))
        print(f"spec={result.spec_path}")
        if result.model_path is not None:
            print(f"model={result.model_path}")
        if result.checkpoint_dir is not None:
            print(f"checkpoints={result.checkpoint_dir}")
    elif args.command == "fetch-loop":
        curriculum_stage_env_ids = ()
        env_id = args.env_id
        if args.curriculum == "basic-to-final":
            curriculum_stage_env_ids = (
                FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
            )
            env_id = FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID
        elif args.curriculum == "final-to-return":
            curriculum_stage_env_ids = (
                FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
            )
            env_id = FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID
        elif args.curriculum == "basic-to-final-return":
            curriculum_stage_env_ids = (
                FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
            )
            env_id = FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID
        elif args.curriculum == "single-random-to-return":
            curriculum_stage_env_ids = (
                FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
                FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
                FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
                FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID,
                FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID,
            )
            env_id = FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID
        elif args.curriculum == "two-to-two-return":
            curriculum_stage_env_ids = (
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
            )
            env_id = FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID
        elif args.curriculum == "two-over-wall-return":
            curriculum_stage_env_ids = (
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID,
            )
            env_id = FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID
        try:
            result = run_fetch_loop(
                FetchLoopConfig(
                    env_id=env_id,
                    curriculum_stage_env_ids=curriculum_stage_env_ids,
                    chunk_timesteps=args.chunk_timesteps,
                    seed=args.seed,
                    output_dir=args.output_dir or next_run_dir(f"fetch_loop_{args.env_id}_seed{args.seed}"),
                    n_envs=args.n_envs,
                    learning_starts=args.learning_starts,
                    checkpoint_interval=args.checkpoint_interval,
                    eval_episodes=args.eval_episodes,
                    success_threshold=args.success_threshold,
                    max_iterations=args.max_iterations,
                    resume_from=args.resume_from,
                    dry_run=args.dry_run,
                    visual_approval_required=args.curriculum == "single-random-to-return",
                    visual_approval_timeout_seconds=args.visual_approval_timeout_seconds,
                    visual_approval_poll_interval_seconds=args.visual_approval_poll_interval_seconds,
                )
            )
        except FetchDependencyError as exc:
            parser.error(str(exc))
        print(f"spec={result.spec_path}")
        print(f"evals={result.eval_path}")
        print(f"success={result.success}")
        if result.model_path is not None:
            print(f"model={result.model_path}")
        if result.video_path is not None:
            print(f"video={result.video_path}")
    elif args.command == "improve-loop":
        result = run_improvement_loop(
            ImprovementLoopConfig(
                output_dir=args.output_dir or next_run_dir("improvement_loop"),
                handoff_log_path=args.handoff_log_path,
                max_iterations=args.max_iterations,
                max_call_attempts=args.max_call_attempts,
                initial_score=args.initial_score,
                target_score=args.target_score,
                simulated_gain=args.simulated_gain,
                fail_first_planner_call=args.fail_first_planner_call,
            )
        )
        print(f"state={result.state_path}")
        print(f"success={result.success}")
        print(f"final_score={result.final_score}")
        print(f"iterations={result.iterations_completed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
