# RobotRL learning_4 - Single-object random generalization

## Goal

learning_4 resets the direction after the fixed-position multi-object lanes. The target is not a memorized routine for one known object coordinate. The target is a single-object policy that can reliably find, grasp, lift, carry, place into the collidable box, and return home when the object starts at randomized positions in the robot-front workspace.

Only after this single-object randomized skill is visually and numerically stable should the project move back to two random objects.

## Stage Plan

| Stage | Environment | Object start radius | Success gate |
| --- | --- | ---: | --- |
| 0 | `RobotRLFetchBoxPlaceBasicRandomNarrow-v0` | `0.02` | Basic in-box placement from a narrow random start range |
| 1 | `RobotRLFetchBoxPlaceBasicRandomMedium-v0` | `0.05` | Basic in-box placement from a wider start range |
| 2 | `RobotRLFetchBoxPlaceBasicRandomWide-v0` | `0.08` | Basic in-box placement from the wide robot-front range |
| 3 | `RobotRLFetchBoxPlaceRandomWide-v0` | `0.08` | Strict final in-box placement from the wide range |
| 4 | `RobotRLFetchBoxPlaceRandomWideReturnHome-v0` | `0.08` | Strict final in-box placement plus gripper/end-effector home return |
| 5 | Planned next lane | random 2 objects | Only after Stage 4 passes metrics and video review |

## Stage Advancement Rule

Do not advance on scalar metrics alone.

Each stage can advance only when both gates pass:

1. Numeric gate:
   - `success_rate >= 0.8` over the configured eval episodes.
   - The eval record has nonzero episodes and a rollout video/GIF artifact.
   - For return-home stages, diagnostics must show home return while final placement remains true.
2. Visual gate:
   - Review the latest rollout GIF/video before accepting the stage.
   - The visible behavior must show a real approach, grasp or stable contact, lift/carry, over-wall or physically valid placement path, release/settle in the box, and home return when required.
   - Reject scalar success if the object or arm passes through the box, tray, shelf, or table, if the object slides/teleports into success, or if success is credited without a stable physical pick-and-place.

If the numeric gate is met but video has not been reviewed, r30o must classify the state as `아직 애매함` and hold the stage. It should report the exact video path that needs inspection instead of advancing or changing code.

For `single-random-to-return` runs, the loop enforces the visual gate directly:

- Eval records must pass trajectory diagnostics for the selected video episode: object starts outside the target zone, object moves materially, gripper gets close to the object, object lifts/carries, the selected episode succeeds, and return-home stages preserve place-return success.
- Eval records expose `video_episode_index`, `video_episode_success`, `video_initial_object_goal_distance`, `video_object_motion_distance`, `video_min_gripper_object_distance`, `video_max_object_lift`, `video_place_return_success`, and `video_return_home_success`.
- The loop waits for a sibling approval marker for the exact GIF hash before it advances or completes a stage.
- Approval marker path: same stem as the GIF with `.approved.json`, for example `stage_05_iteration_043_rollout.approved.json`.

Approval marker schema:

```json
{
  "schema_version": 1,
  "approved": true,
  "reviewer": "r30o-orchestrator",
  "tool": "visual-review",
  "reviewed_gif_path": "runs\\learning_4\\...\\stage_05_iteration_043_rollout.gif",
  "artifact_sha256": "<sha256 of reviewed GIF>",
  "criteria": {
    "approach": {"passed": true},
    "stable_contact_or_grasp": {"passed": true},
    "lift_or_carry": {"passed": true},
    "collidable_box_placement": {"passed": true},
    "home_return": {"passed": true},
    "no_penetration_sliding_or_teleport": {"passed": true}
  }
}
```

## R30O Judgment

Every r30o run judges first and classifies exactly one state:

- `진전 있음`: metrics improve or the stage completes, and video evidence is physically valid.
- `아직 애매함`: training is running, metrics are inconclusive, or numeric success exists but video has not been checked.
- `명백히 아님`: metrics are flat in the wrong direction, diagnostics contradict the goal, or video shows penetration, teleport/slide success, fixed-position overfitting, or success without stable grasp/place.

For `진전 있음` or `아직 애매함`, r30o must not modify code. For `명백히 아님`, r30o uses executor/coding and verifier/evaluation subagents and only accepts a correction when verifier score is greater than 90.

## Active Runs

### run_001_single_object_random_generalization_seed7

Command:

```powershell
python -m robotrl.cli fetch-loop --curriculum single-random-to-return --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_4\run_001_single_object_random_generalization_seed7
```

Notes:

- This run started from scratch to avoid carrying fixed-coordinate behavior from earlier single-object and two-object lanes.
- Final scalar metrics passed at iteration 43, but visual review rejected the artifact as insufficient because the GIF did not clearly prove the full approach, grasp/contact, lift/carry, placement, and home-return sequence.
- This run is not accepted as final learning_4 completion.

### run_002_single_object_random_generalization_visual_gate_seed7

Command:

```powershell
python -m robotrl.cli fetch-loop --curriculum single-random-to-return --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --visual-approval-timeout-seconds 1800 --visual-approval-poll-interval-seconds 30 --output-dir runs\learning_4\run_002_single_object_random_generalization_visual_gate_seed7
```

Notes:

- This run restarts the same random generalization lane with enforced visual approval and selected-video trajectory diagnostics.
- r30o should inspect any pending GIF, create the approval marker only when the checklist is actually true, and let the same running loop advance after the marker is detected.
- The next learning direction after a valid Stage 4 completion is two random objects, not fixed object slots.
