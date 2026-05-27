# RobotRL

RobotRL is starting as a small, dependency-light multi-agent learning harness.
The first environment is intentionally simple: two tabular Q-learning agents
learn to coordinate in a 1D line world and meet at a shared target.

## Quickstart

```powershell
python -m unittest discover -s tests
python -m robotrl.cli train --episodes 60 --seed 7
python -m robotrl.cli train --env robot_arm --episodes 200 --seed 7
python -m robotrl.cli fetch-train --dry-run --total-timesteps 2000000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --seed 7
python -m robotrl.cli fetch-loop --curriculum basic-to-final --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7
python -m robotrl.cli fetch-loop --curriculum final-to-return --resume-from runs\learning\run_014_fetch_box_basic_to_final_curriculum_seed7\success_model.zip --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning\run_015_fetch_box_final_to_return_home_seed7
python -m robotrl.cli fetch-loop --curriculum two-to-two-return --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7
python -m robotrl.cli fetch-loop --curriculum two-over-wall-return --resume-from runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7\success_model.zip --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_3\run_003_multi_object_2_over_wall_basic_slots_seed7
```

When `--output-dir` is omitted, the CLI writes each run under `runs\learning`
with the next execution-order number, for example:

- `runs\learning\run_001_line_world_seed7\metrics.json`
- `runs\learning\run_001_line_world_seed7\policy.json`

## Current Harness

- Environment: `robotrl.envs.line_world.LineWorldEnv`
- Robot arm environment: `robotrl.envs.robot_arm.RobotArmReachEnv`
- Fetch environment target: `RobotRLFetchBoxPlace-v0`, a Gymnasium-Robotics Fetch
  pick-and-place variant with a fixed table box placement zone
- Fetch curriculum restart target: `RobotRLFetchBoxPlaceBasicCurriculum-v0`,
  a right-side box lane with a taller physical tray and lenient first-stage
  success for object-in-box placement
- Fetch return-home target: `RobotRLFetchBoxPlaceReturnHome-v0`, a final-stage
  lane that keeps the physical in-box success gate and also requires the
  gripper/end-effector to return near its initial home position
- Fetch multi-object target: `RobotRLFetchBoxPlaceTwoSequentialReturnHomeCued-v0`,
  a two-object sequential lane that appends a one-hot active-object cue to the
  observation, then requires both objects to stay in the collidable box before
  the gripper returns home
- Fetch multi-object curriculum target:
  `RobotRLFetchBoxPlaceTwoSequentialBasicCued-v0`, an easier first
  `learning_2` stage that keeps the 27-value active-cue observation while using
  the wider basic in-box gate before advancing to strict cued placement and
  cued return-home stages
- Learner: `robotrl.agents.q_learning.QLearningAgent`
- Fetch learner: SAC + HER replay buffer through Stable-Baselines3
- Orchestrator: `robotrl.harness.train`
- CLI: `python -m robotrl.cli train ...` and `python -m robotrl.cli fetch-train ...`

The harness reports both scalar success and behavior-quality indicators such as
last-window step count, team reward, timeout count, and per-episode distance.
This keeps the loop from treating `success_rate` as the only evidence of useful
learning.

## Fetch Training Conditions

Fetch training uses SAC and `MultiInputPolicy`. The base/final
`RobotRLFetchBoxPlace-v0` contract keeps the Fetch robot arm and movable object
from `FetchPickAndPlace-v4`, but fixes the target to a right-side table box zone
centered at `(x=1.42, y=0.58)`. Final success requires the object to be inside
the stricter XY zone and at table-target height, instead of merely reaching an
airborne target.

For R30O restarts, use `fetch-loop --curriculum basic-to-final`. The loop starts
with `RobotRLFetchBoxPlaceBasicCurriculum-v0`, which reports `inside_box`,
`basic_success`, and `final_success` diagnostics. When the basic stage reaches
the configured gate, the same loop advances automatically to
`RobotRLFetchBoxPlaceRightCurriculum-v0`, which preserves the stricter final
contract. The default long-run configuration is 2,000,000 timesteps, 6 vectorized
environments, `learning_starts=10000`, and 50,000-timestep checkpoint intervals.
Use `--dry-run` first to write and inspect the exact training spec without
requiring MuJoCo dependencies.

For the run_015 continuation from run_014, use `fetch-loop --curriculum
final-to-return --resume-from
runs\learning\run_014_fetch_box_basic_to_final_curriculum_seed7\success_model.zip`.
The return-home lane records `home_distance`, `return_home_success`, and
`place_return_success` diagnostics, and `eval_results.json` summarizes them as
`mean_home_distance`, `return_home_success_rate`, and
`place_return_success_rate`. Success requires the object to remain inside the
strict collidable box target and the gripper to be near its initial home
position in the same episode. The dense return-home reward only adds home-return
progress after strict final placement is true, so it gives a usable signal for
moving the gripper home without weakening the final in-box + collidable tray +
home return success contract.

If `run_015` is still running, do not overwrite it. To restart R30O after the
return-home signal correction, resume the completed placement-stage checkpoint
into a new run folder:

```powershell
python -m robotrl.cli fetch-loop --env-id RobotRLFetchBoxPlaceReturnHome-v0 --resume-from runs\learning\run_015_fetch_box_final_to_return_home_seed7\checkpoints\stage_01_complete_model.zip --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning\run_016_fetch_box_return_home_signal_seed7
```

Use `fetch-loop` for autonomous training. It repeats training chunks, writes
checkpoints, evaluates the latest policy, records a rollout GIF, appends
`eval_results.json`, and keeps going until `success_rate >= 0.8`.

For the `learning_2` multi-object lane, use the active-object-cue three-stage
curriculum so stage 1 learns two-object sequential placement with the wider
basic in-box gate, stage 2 restores strict two-object placement without the
home gate, and stage 3 restores the existing return-home success contract. The
cued envs append a two-value one-hot cue to the observation, so they
intentionally start a new policy. Old run16/run002 checkpoints remain
compatible with the legacy non-cued `RobotRLFetchBoxPlaceTwoSequential-v0` and
`RobotRLFetchBoxPlaceTwoSequentialReturnHome-v0` env IDs only.

```powershell
python -m robotrl.cli fetch-loop --curriculum two-to-two-return --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7
```

The lane writes multi-object diagnostics including `object_count`,
`objects_in_box_count`, `object0_in_box`, `object1_in_box`,
`all_objects_in_box`, `multi_place_success`, and
`multi_place_return_success`. R30O should treat scalar success as invalid if
rollout video or diagnostics show tray, box, or shelf penetration, or if
return-home success is reached after either object leaves the box.

The `learning_3` lane tightens that contract with
`RobotRLFetchBoxPlaceTwoSequentialOverWallBasicCued-v0`,
`RobotRLFetchBoxPlaceTwoSequentialOverWallCued-v0`, and
`RobotRLFetchBoxPlaceTwoSequentialOverWallReturnHomeCued-v0`. Those envs expose
`object0_valid_box_entry`, `object1_valid_box_entry`, and
`valid_box_entry_count`; an object is not credited as placed unless it first
clears the tray wall from above. The basic over-wall stage keeps that physical
entry latch while using the wider basic landing gate, so object1 can learn a
valid over-wall entry after object0 before the strict placement and return-home
stages. The over-wall two-object envs also give object1 a separate in-box target
slot after object0 is placed, so the active-object cue switches to a physically
reachable second placement instead of asking both objects to occupy the same
tight final point. This prevents a final in-box coordinate from masking a
wall-penetration trajectory while keeping object1 learnable.

## Reusable Training Protocol

Use **R30O Protocol** to refer to the 30-minute orchestrated RobotRL workflow.
The contract is documented in `docs/robotrl_30min_orchestrator_protocol.md`.
